# -*- coding: utf-8 -*-
from twisted.internet.protocol import Protocol
from twisted.internet import reactor
import logging
import struct 
import ctypes
import Tools
from c2w.main.client_model import c2wClientModel
from c2w.main.constants import ROOM_IDS
from Tools import USER_STATES
logging.basicConfig()
moduleLogger = logging.getLogger('c2w.protocol.tcp_chat_client_protocol')


class c2wTcpChatClientProtocol(Protocol):

    def __init__(self, clientProxy, serverAddress, serverPort):
        """
        :param clientProxy: The clientProxy, which the protocol must use
            to interact with the Graphical User Interface.
        :param serverAddress: The IP address (or the name) of the c2w server,
            given by the user.
        :param serverPort: The port number used by the c2w server,
            given by the user.

        Class implementing the UDP version of the client protocol.

        .. note::
            You must write the implementation of this class.

        Each instance must have at least the following attribute:

        .. attribute:: clientProxy

            The clientProxy, which the protocol must use
            to interact with the Graphical User Interface.

        .. attribute:: serverAddress

            The IP address (or the name) of the c2w server.

        .. attribute:: serverPort

            The port number used by the c2w server.
        .. attribute:: seqNbr

            the sequence number of the message.  For each
            client we define a unique sequence number that will be incremented
            each time when sending a message packet. 
        
        .. attribute:: counter

            A counter to control the number of tries 
            
        .. attribute:: client model
            
            The client model (database), wich the protocol use
            to store users relative informations.
            
        ..attribute:: state
            
            An attribute that store the actual state of the user,
            it is manly used to react correctly to acknowledgement.
        
        ..attribute:: userName
            
            A string used to store the actual userName.
        
        ..attribute:: roomName
            
            An attribute used to store the actual user room.
        
        ..attribute:: msgQueue
            
            A list used as a queue to store messages to be sent.
        
        ..attribute::ackReceived
            
            A bolean used to know whether the first message
            acknowledgement has ben received or not.

        .. note::
            You must add attributes and methods to this class in order
            to have a working and complete implementation of the c2w
            protocol.        .. note::
            You must add attributes and methods to this class in order
            to have a working and complete implementation of the c2w
            protocol.
        """
        self.serverAddress = serverAddress
        self.serverPort = serverPort
        self.clientProxy = clientProxy
        self.timer                = None
        self.seqNbr               = 0
        self.counter              = 0
        self.clientModel          = c2wClientModel()
        self.state                = USER_STATES.DISCONNECTED
        self.userName             = None
        self.roomName             = None
        self.msgQueue             = []
        self.ackRcieved           = True
        self.userBufStr           = ''

    def sendLoginRequestOIE(self, userName):
        """
        :param string userName: The user name that the user has typed.

        The client proxy calls this function when the user clicks on
        the login button.
        """
        self.userName = userName
        self.state = USER_STATES.CONNECTING
        msgBuf = self.constructMsgBuf(self.seqNbr, 1, userName)
        self.transport.write(msgBuf.raw)

        
        print("\n----->login message sent")
        self.manageTimer(self.sendLoginRequestOIE,(userName,))
        moduleLogger.debug('loginRequest called with username=%s', userName)

    def sendChatMessageOIE(self, message, rappel=False):
        """
        :param message: The text of the chat message.
        :type message: string

        Called by the client proxy  when the user has decided to send
        a chat message
        .. note::
           This is the only function handling chat messages, irrespective
           of the room where the user is.  Therefore it is up to the
           c2wChatClientProctocol or to the server to make sure that this
           message is handled properly, i.e., it is shown only by the
           client(s) who are in the same room.
        """    
        msgBuf = self.constructMsgBuf(self.seqNbr, 13, message)
        if rappel == False : 
            if self.ackRcieved is True :
                self.transport.write(msgBuf.raw)
                print("\n----->message sent to server : "+ message+ " seq ("+str(self.seqNbr)+")")
                self.manageTimer(self.sendChatMessageOIE,(message,True))
                self.ackRcieved = False
            else :
                print("\n----->message added to queue : "+ message+ " seq ("+str(self.seqNbr)+")")
                self.msgQueue =[(message,13)] + self.msgQueue
        else :
            self.transport.write(msgBuf.raw)
            print("\n----->message sent to server : "+ message+ " seq ("+str(self.seqNbr)+")")
            self.manageTimer(self.sendChatMessageOIE,(message,True))

    def sendJoinRoomRequestOIE(self, roomName):
        """
        :param roomName: The room name (or movie title.)

        Called by the client proxy  when the user
        has clicked on the watch button or the leave button,
        indicating that she/he wants to change room.

        .. warning:
            The controller sets roomName to
            c2w.main.constants.ROOM_IDS.MAIN_ROOM when the user
            wants to go back to the main room.
        """
        print ("\n----->join room requested")
        self.roomName = roomName
        self.state = USER_STATES.TO_ROOM_REQUEST_PENDING
        # for the main room the movieId to be sent is 0
        if(roomName == ROOM_IDS.MAIN_ROOM):
            movieId = 0
        #otherwise it's the movieId of the movieRoom  
        else:
            movie = self.clientModel.getMovieByTitle(roomName)
            movieId = movie.movieId
            
        msgBuf = self.constructMsgBuf(self.seqNbr, 3, movieId)
        
        self.transport.write(msgBuf.raw)
        self.manageTimer(self.sendJoinRoomRequestOIE,(roomName,))

            
    def sendAcknowledgementOIE(self,seqNbr):
        """
        :param seqNbr : the sequence of the message received
        
        Called by the client protocol to acknowledge
        a received message.
        """
        msgBuf    = self.constructMsgBuf(seqNbr, 0)
        self.transport.write(msgBuf.raw)
        
    
    def sendLeaveSystemRequestOIE(self):
        """
        Called by the client proxy  when the user
        has clicked on the leave button in the main room.
        """
        print("\n----->leave system request sent")
        self.state = USER_STATES.TO_OUT_OF_THE_SYSTEM_ROOM_REQUEST_PENDING
        msgBuf = self.constructMsgBuf(self.seqNbr, 2)
        self.transport.write(msgBuf.raw)
        self.manageTimer(self.sendLeaveSystemRequestOIE,())

    def dataReceived(self, data):
        """
        :param data: The message received from the server
        :type data: A string of indeterminate length

        Twisted calls this method whenever new data is received on this
        connection.
        """
        msgType=None
        msgLen =0
        self.userBufStr=self.userBufStr + data[0:]

        if len(self.userBufStr) >= 2: 
            msgSeq, msgType = Tools.getHead(self.userBufStr) 
            if(msgType in (0,5,6)):
                self.dataCompleteReceived(self.userBufStr[0:2])
                if self.userBufStr[2:] != '':
                    temp = self.userBufStr[2:]
                    self.userBufStr=''
                    self.dataReceived(temp)
                self.userBufStr=''

            elif  msgType in (7,8,14,9,10,11,12):
                if len(self.userBufStr) >= 4:
                    msgLen=Tools.getLen(self.userBufStr)
                    if len(self.userBufStr) >= msgLen:
                        self.dataCompleteReceived(self.userBufStr[0:msgLen] )
                        if self.userBufStr[msgLen:] != '':
                            temp = self.userBufStr[msgLen:]
                            self.userBufStr=''
                            self.dataReceived(temp)                        
                        self.userBufStr=''      
                    
    def dataCompleteReceived(self, datagram):
        """
        :param string datagram: the payload of the UDP packet.
        :param host: the IP address of the source.
        :param port: the source port.

        Called **by Twisted** when the client has received a UDP
        packet.
        """
        msgSeq, msgType = Tools.getHead(datagram)
        
        #Acknowledgement received 
        if (msgType == 0):
            print("\n<-----acknowlegment received")
            self.timer.cancel()
            self.counter = 0
            self.seqNbr += 1
            self.ackRcieved = True
            if self.msgQueue != [] :
                lastMsgData, lastMsgType = self.msgQueue.pop()
                if lastMsgType is 13 :
                    self.sendChatMessageOIE(lastMsgData)
            #If join room or leave system requested 
            if self.state == USER_STATES.TO_OUT_OF_THE_SYSTEM_ROOM_REQUEST_PENDING :
                self.clientProxy.leaveSystemOKONE()
            elif self.state == USER_STATES.TO_ROOM_REQUEST_PENDING :
                self.state = USER_STATES.IN_ROOM
                self.clientModel.updateUserChatroom(self.userName, self.roomName)
                self.clientProxy.joinRoomOKONE()
                
                
        #Login ok received
        elif (msgType is 5):
            print("\n<-----login ok received")
            print("\n----->acknowledgment sent")
            #when login ok recieved the user must be added to dataBase
            self.roomName = ROOM_IDS.OUT_OF_THE_SYSTEM_ROOM
            self.clientModel.addUser(self.userName, None, self.roomName)
        
        #Login failed
        elif(msgType is 6):
            print("\n<-----Login failed received ")
            print("\n----->acknowledgment sent")
            self.clientProxy.connectionRejectedONE("Nom d'utilisateur indisponible")   
            
        else :
            msgLen  = Tools.getLen(datagram)           
            #User list received   
            if(msgType is 7):
                print("\n<-----User list received ")
                print("\n----->acknowledgment sent")
                self.userListRecieved(datagram, msgLen)
                    
            #Movie list received
            elif(msgType is 8):
                print("\n<-----Movie list received")
                print("\n----->acknowledgment sent")
                self.movieListReceived(datagram, msgLen)
                    
            #Chat message received       
            elif(msgType is 14):
                print("\n<-----chat message received")
                print("\n----->acknowledgment sent")
                self.chatMessageRecieved(datagram, msgLen) 
                
            #Notification received
            elif(msgType in (9, 10, 11, 12) ):
                print("\n<-----notification message received")
                print("\n----->acknowledgment sent")
                self.notificationRecieved(datagram, msgLen, msgType)
                
        #Interface update after receiving movie and user lists  
        if self.state == USER_STATES.INITIALAZATION_COMPLETE :
                print("\n**initialization step complete**")
                self.state = USER_STATES.IN_ROOM
                self.roomName = ROOM_IDS.MAIN_ROOM              
                userList = []
                for user in self.clientModel.getUserList():
                    movie = self.clientModel.getMovieById(user.userChatRoom)
                    if(movie == None):
                        userList = userList + [(user.userName, ROOM_IDS.MAIN_ROOM)]
                        self.clientModel.updateUserChatroom(user.userName, ROOM_IDS.MAIN_ROOM)
                    else :
                        userList = userList + [(user.userName, movie.movieTitle)]
                        self.clientModel.updateUserChatroom(user.userName, movie.movieTitle)
                    
                movieList = [(m.movieTitle,m.movieIpAddress,m.moviePort) for m in self.clientModel.getMovieList()]
                self.clientProxy.initCompleteONE(userList, movieList);
        
        #If the message received is not an Ack send acknowledgement 
        if(msgType != 0 ) :
            self.sendAcknowledgementOIE(msgSeq)   
            
    def manageTimer(self, sendMessage,  args):
        """
        :param funcion sendMessage : the function that sends the message
        :param string args    : the arguments of the function
        
        called whenever  a message is sent to activate/desactivate
        the timer.
        """
        if(self.counter < 100):
            self.counter+=1
            self.timer = reactor.callLater(0.5,sendMessage,*args)
        else :
            self.counter = 0
            
            
    def constructMsgBuf(self, seqNbr, msgType, msgData = ''):
        """
        :param int seqNbr     : the sequence number field of the message
        :param int msgType    : the message Type field
        :param string msgData : the message data field 
        
        this function constract the message buffer for 
        all messages for the client to send
        supported types :0, 1, 2, 3, 13
        """
        """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
        |seqNbr (11 bits) + msgtype (5bits) | msgLen(2bytes) (+ message (variable length))|
        |         msgHead(2bytes)           |                                             |
        """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""       
        msgHead = (seqNbr<<5) + msgType 
        if(msgType is 0):
        #for types 0 (acknowledgement)
            msgLen = 2
            msgBuf = ctypes.create_string_buffer(msgLen)
            struct.pack_into('>H', msgBuf, 0, msgHead)       
        #for type 3 (join room)
        elif(msgType is 3):
            msgLen = 5 
            msgBuf = ctypes.create_string_buffer(msgLen)
            struct.pack_into('>HHB', msgBuf, 0, msgHead, msgLen, msgData)
        #for types 1 (login), 2(disconnect), 13(chat message)
        else:   
            msgLen = 4 + len(msgData)
            msgBuf = ctypes.create_string_buffer(msgLen)
            struct.pack_into('>HH'+str(len(msgData))+'s', msgBuf, 0, msgHead, msgLen, msgData)
        return msgBuf 
    
    def userListRecieved(self, datagram, msgLen):
        """
        :param ctypes.c_char_Array_3 datagram : the message packet
        :param int msgLen    : the message length
        
        This function is called by the protocol when the user list message
        is recieved.It unpacks the message packet, extract users information
        and fill the database model.
        """
        if self.state is USER_STATES.MOVIE_LIST_RECIEVED:
            self.state = USER_STATES.INITIALAZATION_COMPLETE
        else : self.state = USER_STATES.USER_LIST_RECIEVED
        offset = 4
        while (offset < msgLen):
                    f = struct.unpack_from('!BH',datagram,offset)
                    userChatRoom, userNameLen  = f[0:2]
                    f = struct.unpack_from('!BH'+str(userNameLen)+'s',datagram,offset)
                    userName    = f[2]
                    if(userChatRoom == 0): 
                        userChatRoom = ROOM_IDS.MAIN_ROOM

                    if(self.userName != userName):
                        self.clientModel.addUser(userName, None, userChatRoom)
                    offset     += 3 + userNameLen
                    
    def movieListReceived(self, datagram, msgLen):
        """
        :param ctypes.c_char_Array_3 datagram : the message packet
        :param int msgLen    : the message length
        
        This function is called by the protocol when the movie list message
        is recieved.It unpacks the message packet, extract movies information
        and fill the database model.
        """
        if self.state is USER_STATES.USER_LIST_RECIEVED:
            self.state = USER_STATES.INITIALAZATION_COMPLETE
        else : self.state = USER_STATES.MOVIE_LIST_RECIEVED
        offset = 4
        while (offset < msgLen):
                    f = struct.unpack_from('!BIHH',datagram,offset)
                    movieId, host, port, movieNameLen    = f[0:4]
                    f = struct.unpack_from('!BIHH'+str(movieNameLen)+'s',datagram,offset)
                    movieName    = f[4]
                    self.clientModel.addMovie(movieName,host,port,movieId)
                    offset     += 9 + movieNameLen
    
    def notificationRecieved(self, datagram, msgLen, msgType):
        """
        :param ctypes.c_char_Array_3 datagram : the message packet
        :param int msgLen    : the message length
        :param int msgType : the message type
        
        This function is called by the protocol when a notification message
        is recieved.It unpacks the message packet and update database according
        to data extracted.
        """
        offset = 4
        f = struct.unpack_from('!B'+str(msgLen-5)+'s',datagram,offset)
        movieId, userName  = f[0:2]
        #connection notification recieved
        if msgType is 9 :
            roomName = ROOM_IDS.MAIN_ROOM            
            self.clientModel.addUser(userName, None, ROOM_IDS.MAIN_ROOM) 
        #To main room notification recieved
        elif msgType is 11:
            roomName = ROOM_IDS.MAIN_ROOM
        #Leave the system notification recieved
        elif msgType is 10:
            roomName = ROOM_IDS.OUT_OF_THE_SYSTEM_ROOM
        #moving to movie room notification recieved   
        else:
            roomName = self.clientModel.getMovieById(movieId).movieTitle 
        #update database and interface
        self.clientModel.updateUserChatroom(userName, roomName)
        self.clientProxy.userUpdateReceivedONE(userName, roomName)
        
    def chatMessageRecieved(self, datagram, msgLen):
        """
        :param ctypes.c_char_Array_3 datagram : the message packet
        :param int msgLen    : the message length
        
        This function is called by the protocol when a chat message
        is recieved.It unpacks the message packet, extract the chat message
        and update the interface to show message in the chat room.
        """
        offset = 4
        f = struct.unpack_from('!H',datagram,offset)
        userNameLen  = f[0]
        f = struct.unpack_from('!H'+str(userNameLen)+'s'+str(msgLen-6-userNameLen)+'s',datagram,offset)
        userName, message    = f[1:3]
        self.clientProxy.chatMessageReceivedONE(userName, message)
