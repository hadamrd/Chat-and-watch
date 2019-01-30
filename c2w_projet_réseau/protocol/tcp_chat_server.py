# -*- coding: utf-8 -*-
from twisted.internet.protocol import Protocol
import logging
import Tools
import ctypes
import struct
from twisted.internet import reactor
from c2w.main.constants import ROOM_IDS

logging.basicConfig()
moduleLogger = logging.getLogger('c2w.protocol.tcp_chat_server_protocol')


class c2wTcpChatServerProtocol(Protocol):

    def __init__(self, serverProxy, clientAddress, clientPort):
        """
        :param serverProxy: The serverProxy, which the protocol must use
            to interact with the user and movie store (i.e., the list of users
            and movies) in the server.
        :param clientAddress: The IP address (or the name) of the c2w server,
            given by the user.
        :param clientPort: The port number used by the c2w server,
            given by the user.

        Class implementing the TCP version of the client protocol.

        .. note::
            You must write the implementation of this class.

        Each instance must have at least the following attribute:

        .. attribute:: serverProxy

            The serverProxy, which the protocol must use
            to interact with the user and movie store in the server.

        .. attribute:: clientAddress

            The IP address (or the name) of the c2w server.

        .. attribute:: clientPort

            The port number used by the c2w server.
			
        .. attribute:: seqNbr

			the sequence number of the message.  For each
            client we define a unique sequence number that will be incremented
            each time when sending a message packet.

        .. attribute:: timer	
		
			After timer, function should be recalled	
		
        .. attribute:: userState

			An attribute that store the actual state of the user,
            it is manly used to react correctly to acknowledgement.

        .. attribute:: counter

			A counter to control the number of tries			

        .. note::
            You must add attributes and methods to this class in order
            to have a working and complete implementation of the c2w
            protocol.

        .. note::
            The IP address and port number of the client are provided
            only for the sake of completeness, you do not need to use
            them, as a TCP connection is already associated with only
            one client.
        """
        self.clientAddress = clientAddress
        self.clientPort = clientPort
        self.serverProxy = serverProxy
        self.seqNbr    = 0
        self.timer     = None
        self.userState = Tools.USER_STATES.CONNECTING
        self.counter   = 0
        self.userBufStr=''
    def dataReceived(self, data):
        """
        :param data: The message received from the server
        :type data: A string of indeterminate length

        Twisted calls this method whenever new data is received on this
        connection.
        """
        msgType=None
        msgLen = 0
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
            if  msgType in (1,2,3,13):
                if len(self.userBufStr) >= 4:
                    msgLen=Tools.getLen(self.userBufStr)

                    if len(self.userBufStr) >= msgLen:
                        self.dataCompleteReceived(self.userBufStr[0:msgLen])

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

        Called **by Twisted** when the server has received a UDP
        packet.
        """
        
        msgSeq, msgType = Tools.getHead(datagram)
        if(msgType == 0):
        #acknowledgement message received
            print("\n<-----ack message received")
            self.seqNbr+= 1
            self.timer.cancel()
            
            if(self.userState is Tools.USER_STATES.LOGIN_OK_PENDING):
            #Login ok ack received
                print("\n----->user list sent")
                self.sendUserList()
                self.userState  =  Tools.USER_STATES.USER_LIST_PENDING

                
            elif(self.userState is Tools.USER_STATES.USER_LIST_PENDING):
            #User list received ack
                print("\n----->movie list sent")
                self.sendMovieList()
                self.userState = Tools.USER_STATES.MOVIE_LIST_PENDING
                
            elif(self.userState is Tools.USER_STATES.MOVIE_LIST_PENDING):
            #Movie list received ack (intialization step complete)
                self.userState  = Tools.USER_STATES.INITIALAZATION_COMPLETE
                user = self.serverProxy.getUserByAddress((self.clientAddress,self.clientPort))
                #update the user statu
                self.serverProxy.updateUserChatroom(user.userName, ROOM_IDS.MAIN_ROOM)
                #notify the other users so that user appear in main room
                for otherUser in self.serverProxy.getUserList():
                    if(otherUser != user):
                        print("\n----->notification message sent to "+otherUser.userName)
                        otherUser.userChatInstance.sendNotification(user)
                self.userState = Tools.USER_STATES.IN_ROOM
                                    
        else :
            msgLen = Tools.getLen(datagram)
            #send acknowledgement
            self.sendAcknowledgement(msgSeq)
           
            if(msgType is 1):
            #A new login request received
                print("\n<-----login request received")
                print("\n----->ack message sent")
                self.seqNbr  = 0
                self.counter = 0
                userName = Tools.getData(datagram,msgLen)
                if(self.serverProxy.userExists(userName)):
                #If user name not available send login rejected
                    self.userState=Tools.USER_STATES.CORRECT_USERNAME_PENDING
                    self.sendLoginReject()
                    print("\n----->login reject sent")
                else:
                #Else send login ok and add the user in data bases
                    #add the user in databases
                    self.serverProxy.addUser(userName, ROOM_IDS.OUT_OF_THE_SYSTEM_ROOM, self, (self.clientAddress,self.clientPort))
                    self.userState = Tools.USER_STATES.LOGIN_OK_PENDING
                    #send the login ok message
                    self.sendLoginOk()
                    print("\n----->login ok sent")
            
                    
            if(msgType in (2,3,13)):
                user  = self.serverProxy.getUserByAddress((self.clientAddress,self.clientPort))
                if(msgType == 3):
                #Joinroom request received
                    print("\n<-----join room received")
                    print("\n----->ack message sent")
                    
                    movieId = Tools.getRoomIdFromData(datagram,msgLen)
                    movie = self.serverProxy.getMovieById(movieId)
                    if(movieId is 0):
                        movieRoom = ROOM_IDS.MAIN_ROOM
                    else:
                        movieRoom = movie.movieTitle
                        self.serverProxy.startStreamingMovie(movieRoom) 
                    self.serverProxy.updateUserChatroom(user.userName, movieRoom)
                    
                       
                    #send notification to the users
                    for otherUser in self.serverProxy.getUserList():
                        if(otherUser != user):
                            otherUser.userChatInstance.sendNotification(user)
                            print("\n----->notification message sent to "+otherUser.userName)
                
                if(msgType is 2):
                #Leave the system message received
                    print("\n<-----leave message received")
                    print("\n----->ack message sent")
                    #Update the client statu
                    self.serverProxy.updateUserChatroom(user.userName, ROOM_IDS.OUT_OF_THE_SYSTEM_ROOM)
                    #send notification to the users
                    for otherUser in self.serverProxy.getUserList():
                        if otherUser is not user:
                            otherUser.userChatInstance.sendNotification(user)
                            print("\n----->notification message sent to "+otherUser.userName)                        
                    #remove user from databases
                    self.serverProxy.removeUser(user.userName)

                if(msgType is 13):
                #Chat messate received
                    print("\n<-----chat message received from "+user.userName)
                    print("\n----->ack message sent")
                    chatMessage = Tools.getData(datagram,msgLen)                   
                    #broadcast the message in the user chatroom
                    for otherUser in self.serverProxy.getUserList():
                        if(otherUser.userChatRoom == user.userChatRoom and otherUser != user):
                            otherUser.userChatInstance.sendChatMessage(user.userName, chatMessage) 
                            print("\n----->chat message sent to "+otherUser.userName)

                 

    def sendLoginOk(self, msgBuf = None):
        """
        :param <tuple, 'tuple>  userAdrs   : the user adress (host,port). 
        :param ctypes.c_char_Array_3 msgBuf (optional) : if we want to 
         send a bufferMsg premade this argument can be usefull.

         This function sends the login OK(type 5) message to a user 
         and call the function that manage the timer. 
         The construction of the message buffer is done using
         constructUser056MsgBufer (refer to it's doc to see message format)
         
         """
        msgType = 5
        if(msgBuf is None):
            msgBuf = self.constructUser056MsgBufer(self.seqNbr, msgType)
            
        self.transport.write(msgBuf.raw)
        self.manageTimer(self.sendLoginOk,(msgBuf,))

    
    def sendLoginReject(self, msgBuf = None):
        """
        :param <tuple, 'tuple>  userAdrs   : the user adress (host,port). 
        :param ctypes.c_char_Array_3 msgBuf (optional) : if we want to 
         send a bufferMsg premade this argument can be usefull.

         This function sends the login rejected (type 6) message to a user 
         and call the function that manage the timer. 
         The construction of the message buffer is done using
         constructUser056MsgBufer (refer to it's doc to see message format)
         
         """
        msgType = 6
        if(msgBuf is None):
            msgBuf  = self.constructUser056MsgBufer(self.seqNbr, msgType) 
            
        self.transport.write(msgBuf.raw)
        self.manageTimer(self.sendLoginReject, (msgBuf,))  
    
    def sendAcknowledgement(self, msgSeq):
        """
        :param <tuple, 'tuple>  userAdrs   : the user adress (host,port). 
        :param ctypes.c_char_Array_3 msgBuf (optional) : if we want to 
         send a bufferMsg premade this argument can be usefull.

         This function sends an acknowledgement(type 0) message porting msgSeq 
         as a sequence number to a user.
         The construction of the message buffer is done using
         constructUser056MsgBufer (refer to it's doc to see message format).
        
         """
        msgType = 0
        msgBuf  = self.constructUser056MsgBufer(msgSeq, msgType)
        self.transport.write(msgBuf.raw)
    
    
    def sendUserList(self,msgBuf = None):
        """
        :param <tuple, 'tuple>  userAdrs   : the user adress (host,port). 
        :param ctypes.c_char_Array_3 msgBuf (optional) : if we want to 
         send a bufferMsg premade this argument can be usefull.

         This function construct and sends the user list to a user
         and call the function that manage the timer. 
         +−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+
         |  Sequence Number    |  Type   |       Packet Length           |
         +−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+
         |    State      |       Username  Length        |Username (var.)|
         +−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+
         .                                                               .
         .                                                               .
         .                                                               .
         """        
        if(msgBuf is None):
            msgType     = 7 
            msgLen      = 4
            msgHead = (self.seqNbr<<5)+ msgType 
            for user in self.serverProxy.getUserList():
                msgLen  += 3 + len(user.userName)
            msgBuf    = ctypes.create_string_buffer(msgLen)
            struct.pack_into(">HH", msgBuf, 0,msgHead,msgLen)
            offset = 4
            for user in self.serverProxy.getUserList():
                movieId=0
                if user.userChatRoom not in  (ROOM_IDS.MAIN_ROOM, ROOM_IDS.OUT_OF_THE_SYSTEM_ROOM) :
                    movieId = self.serverProxy.getMovieByTitle(user.userChatRoom).movieId
                struct.pack_into(">BH"+str(len(user.userName))+'s', msgBuf, offset,
                                 movieId,len(user.userName),user.userName)
                offset += 3 + len(user.userName)
        self.transport.write(msgBuf.raw)
        self.manageTimer(self.sendUserList,(msgBuf,))    
        
        
    def sendMovieList(self,msgBuf=None):
        """
        :param <tuple, 'tuple>  userAdrs   : the user adress (host,port). 
        :param ctypes.c_char_Array_3 msgBuf (optional) : if we want to 
         send a bufferMsg premade this argument can be usefull. 

        This function construct and sends the movie list to a user
        and call the function that manage the timer. 
        +−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+
        |  Sequence Number    |  Type   |        msgLen(2bytes)         |
        |        msgHead(2bytes)        |                               |
        +−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+
        |   movieID(1byte)    |                      Host...            |
        +−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+
        |    Host(3bytes)     |            Port(2bytes)       | Name..  |
        +−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+
        | Length(2bytes)     |      MovieTitle (variable length)        |
        +−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+
        .                                                               .
        .                                                               .
        .                                                               .
        """
        if (msgBuf is None):
            msgType     = 8 
            msgLen      = 4
            msgHead = (self.seqNbr<<5)+ msgType 
            for movie in self.serverProxy.getMovieList():
                msgLen  += 9 + len(movie.movieTitle)
            msgBuf    = ctypes.create_string_buffer(msgLen)
            struct.pack_into(">HH", msgBuf, 0, msgHead,msgLen)
            offset = 4
            for movie in self.serverProxy.getMovieList():
                adrs = movie.movieIpAddress.split(".")
                struct.pack_into(">5BHH"+str(len(movie.movieTitle))+'s', msgBuf, offset, movie.movieId,
                                 int(adrs[0]), int(adrs[1]), int(adrs[2]), int(adrs[3])
                                 , movie.moviePort,len(movie.movieTitle),movie.movieTitle)
                offset += 9 + len(movie.movieTitle)
        self.transport.write(msgBuf.raw)
        self.manageTimer(self.sendUserList,(msgBuf,))
        

    def sendNotification(self, sender, msgBuf=None):
        """
        :param c2wUser user       : the message transmitter.  
        :param c2wUser otherUser  : the message reciever.
        :param ctypes.c_char_Array_3 msgBuf (optional) : if we want to 
         send a bufferMsg premade this argument can be usefull. 
         
        This function send a notification type message from
        user to otherUser and call the function that manage the timer. 
       +−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+
       |  Sequence Number    | Type   |       msgLen(2bytes)           | 
       |        msgHead(2bytes)       |                                |
       +−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+
       |    MovieID(1byte)   |        Username (variable length)       |
       +−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+
        """
        if(msgBuf is None ):
            if (sender.userChatRoom  is ROOM_IDS.MAIN_ROOM):
                if(sender.userChatInstance.userState is Tools.USER_STATES.INITIALAZATION_COMPLETE):
                    msgType = 9
                else : 
                    msgType = 11
                movieId = 0
            elif(sender.userChatRoom is ROOM_IDS.OUT_OF_THE_SYSTEM_ROOM):
                msgType = 10
                movieId = 0
            else :
                msgType = 12
                movieId = self.serverProxy.getMovieByTitle(sender.userChatRoom).movieId
                
            msgHead = (self.seqNbr<<5)+ msgType
            msgLen  = 5 + len(sender.userName)
            msgBuf  = ctypes.create_string_buffer(msgLen)
            struct.pack_into('>HHB'+str(len(sender.userName))+'s',
                             msgBuf, 0, msgHead, msgLen, movieId, sender.userName)
        self.transport.write(msgBuf.raw)  
        self.manageTimer(self.sendNotification,(sender,msgBuf, ))
          
           
  
    def sendChatMessage(self,senderName, chatMessage, msgBuf=None):
        """
        :param c2wUser user       : the message transmitter. 
        :param string chatMessage : the chat message. 
        :param c2wUser otherUser  : the message reciever.
        :param ctypes.c_char_Array_3 msgBuf (optional) : if we want to 
         send a bufferMsg premade this argument can be usefull. 
        
        This function send a chat message from user to an otherUser
        and call the function that manage the timer.  
        +−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+
        |  Sequence Number    |  Type   |       msgLen(2bytes)          |
        |            msgHead(2bytes)    |                               |
        +−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+
        |  len(user.userName) (2bytes)  |      user.userName(var.)      |
        +−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+−+
        |               chatMessage  (variable length)                  |
        +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        """
        if(msgBuf is None):
            msgType = 14
            msgHead = (self.seqNbr<<5) + msgType
            msgLen  = 6 + len(senderName) + len(chatMessage)
            msgBuf  = ctypes.create_string_buffer(msgLen)
            struct.pack_into('>HHH'+str(len(senderName))+'s'+str(len(chatMessage))+'s', msgBuf,
                             0, msgHead, msgLen, len(senderName), senderName, chatMessage)
        self.transport.write(msgBuf.raw)
        self.manageTimer(self.sendChatMessage,(senderName,chatMessage,msgBuf))

            
    def constructUser056MsgBufer(self, seqNbr, msgType)  :
        """
        :param int msgType            : the message Type field.
        :param <tuple, 'tuple> usrAdrs: the user (host ,port). 
        
        this function constract the message buffer of
        some messages for the server to send and return it. 
        
        Supported types : 0, 5, 6
        ---------------------------------------
        |seqNbr (11 bits) | msgtype (5bits)   | 
        |         msgHead(2bytes)             |                                             
        ---------------------------------------
        """
        msgBuf    = ctypes.create_string_buffer(2)
        msgHead = (seqNbr<<5) + msgType 
        struct.pack_into('>H', msgBuf, 0, msgHead)
        return msgBuf
        
    def manageTimer(self, sendMessage, args):
        """
        :param funcion sendMessage : the function that sends the message.
        :param string args    : the arguments of the function.
        
        called whenever  a message is sent to activate/desactivate
        the timer.The timer calls the function sendMessage after 0.5sec if
        not desactivated.
        To control the timer, his id is stored in the timers dictionary.
        """
        if(self.counter< 100):
            self.counter+= 1
            self.timer   = reactor.callLater(0.5, sendMessage, *args)
        else :
            self.counter= 0
            
