# -*- coding: utf-8 -*-
from twisted.internet.protocol import DatagramProtocol
from c2w.main.lossy_transport import LossyTransport
from twisted.internet import reactor
import logging
import Tools 
import struct

import ctypes
from c2w.main.constants import ROOM_IDS

logging.basicConfig()
moduleLogger = logging.getLogger('c2w.protocol.udp_chat_server_protocol')


class c2wUdpChatServerProtocol(DatagramProtocol):

    def __init__(self, serverProxy, lossPr):
        """
        :param serverProxy: The serverProxy, which the protocol must use
            to interact with the user and movie store (i.e., the list of users
            and movies) in the server.
        :param lossPr: The packet loss probability for outgoing packets.  Do
            not modify this value!

        Class implementing the UDP version of the client protocol.

        .. note::
            You must write the implementation of this class.

        Each instance must have at least the following attribute:

        .. attribute:: serverProxy

            The serverProxy, which the protocol must use
            to interact with the user and movie store in the server.

        .. attribute:: lossPr

            The packet loss probability for outgoing packets.  Do
            not modify this value!  (It is used by startProtocol.)

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
        """

        self.serverProxy = serverProxy
        self.lossPr    = lossPr
        self.seqNbr    = {}
        self.timer     = {}
        self.userState = {}
        self.counter   = {}
        
    def startProtocol(self):
        """
        DO NOT MODIFY THE FIRST TWO LINES OF THIS METHOD!!

        If in doubt, do not add anything to this method.  Just ignore it.
        It is used to randomly drop outgoing packets if the -l
        command line option is used.
        """
        self.transport = LossyTransport(self.transport, self.lossPr)
        DatagramProtocol.transport = self.transport

    def datagramReceived(self, datagram, (host, port)):
        """
        :param string datagram: the payload of the UDP packet.
        :param host: the IP address of the source.
        :param port: the source port.

        Called **by Twisted** when the server has received a UDP
        packet.
        """
        address = (host, port)
        msgSeq, msgType = Tools.getHead(datagram)
        if(msgType == 0):
        #acknowledgement message recieved
            print("\n<-----ack message recieved")
            self.seqNbr[address]+= 1
            self.timer[address].cancel()
            
            if(self.userState[address] is Tools.USER_STATES.LOGIN_OK_PENDING):
            #Login ok ack received
                print("\n----->user list sent")
                self.sendUserList(address)
                self.userState[address]  =  Tools.USER_STATES.USER_LIST_PENDING

                
            elif(self.userState[address] is Tools.USER_STATES.USER_LIST_PENDING):
            #User list received ack
                print("\n----->movie list sent")
                self.sendMovieList(address)
                self.userState[address] = Tools.USER_STATES.MOVIE_LIST_PENDING
                
            elif(self.userState[address] is Tools.USER_STATES.MOVIE_LIST_PENDING):
            #Movie list received ack (intialization step complete)
                self.userState[address]  = Tools.USER_STATES.INITIALAZATION_COMPLETE
                user = self.serverProxy.getUserByAddress(address)
                #update the user statu
                self.serverProxy.updateUserChatroom(user.userName, ROOM_IDS.MAIN_ROOM)
                #notify the other users so that user appear in main room
                for otherUser in self.serverProxy.getUserList():
                    if(otherUser != user):
                        print("\n----->notification message sent to "+otherUser.userName)
                        self.sendNotification(user, otherUser)
                self.userState[address] = Tools.USER_STATES.IN_ROOM
                                    
        else :
            msgLen = Tools.getLen(datagram)
            #send acknowledgement
            self.sendAcknowledgement(msgSeq,(host, port))
            
            if(msgType is 1):
            #A new login request received
                print("\n<-----login request recieved")
                print("\n----->ack message sent")
                self.seqNbr[address]  = 0
                self.counter[address] = 0
                userName = Tools.getData(datagram,msgLen)
                if(self.serverProxy.userExists(userName)):
                #If user name not available send login rejected
                    self.userState[address]=Tools.USER_STATES.CORRECT_USERNAME_PENDING
                    self.sendLoginReject((host, port))
                    print("\n----->login reject sent")
                else:
                #Else send login ok and add the user in data bases
                    #add the user in databases
                    self.serverProxy.addUser(userName, ROOM_IDS.OUT_OF_THE_SYSTEM_ROOM, None, (host, port))
                    self.userState[address] = Tools.USER_STATES.LOGIN_OK_PENDING
                    #send the login ok message
                    self.sendLoginOk((host, port))
                    print("\n----->login ok sent")
            
                    
            if(msgType in (2,3,13)):
                user  = self.serverProxy.getUserByAddress(address)
                if(msgType == 3):
                #Joinroom request received
                    print("\n<-----join room recieved")
                    print("\n----->ack message sent")
                    
                    movieId = Tools.getRoomIdFromData(datagram,msgLen)
                    movie = self.serverProxy.getMovieById(movieId)
                    #print("A new client just joined room : " + str(movieId) )
                    if(movieId is 0):
                        movieRoom = ROOM_IDS.MAIN_ROOM
                    else:
                        movieRoom = movie.movieTitle
                        self.serverProxy.startStreamingMovie(movieRoom) 
                    self.serverProxy.updateUserChatroom(user.userName, movieRoom)
                    
                       
                    #send notification to the users
                    for otherUser in self.serverProxy.getUserList():
                        #if(otherUser != user):
                        self.sendNotification(user, otherUser)
                        print("\n----->notification message sent to "+otherUser.userName)
                
                if(msgType is 2):
                #Leave the system message received
                    print("\n<-----leave message received")
                    print("\n----->ack message sent")
                    #Update the client statu
                    self.serverProxy.updateUserChatroom(user.userName, ROOM_IDS.OUT_OF_THE_SYSTEM_ROOM)
                    #send notification to the users
                    for otherUser in self.serverProxy.getUserList():
                        if(otherUser != user):
                            self.sendNotification(user, otherUser)
                            print("\n----->notification message sent to "+otherUser.userName)                        
                    #remove user from databases
                    self.seqNbr.pop(user.userAddress)
                    self.timer.pop(user.userAddress)
                    self.counter.pop(user.userAddress)
                    self.userState.pop(user.userAddress)
                    self.serverProxy.removeUser(user.userName)

                if(msgType is 13):
                #Chat messate received
                    print("\n<-----chat message recieved from "+user.userName)
                    print("\n----->ack message sent")
                    chatMessage = Tools.getData(datagram,msgLen)                   
                    #broadcast the message in the user chatroom
                    for otherUser in self.serverProxy.getUserList():
                        if(otherUser.userChatRoom == user.userChatRoom and otherUser != user):
                            self.sendChatMessage(user, chatMessage, otherUser) 
                            print("\n----->chat message sent to "+otherUser.userName)

                 

    def sendLoginOk(self, userAdrs, msgBuf = None):
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
            msgBuf = self.constructUser056MsgBufer(self.seqNbr[userAdrs], msgType)
            
        self.transport.write(msgBuf.raw, userAdrs)
        self.manageTimer(userAdrs,self.sendLoginOk,(userAdrs, msgBuf))

    
    def sendLoginReject(self, userAdrs, msgBuf = None):
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
            msgBuf  = self.constructUser056MsgBufer(self.seqNbr[userAdrs], msgType) 
            
        self.transport.write(msgBuf.raw,userAdrs)
        self.manageTimer(userAdrs, self.sendLoginReject, (userAdrs, msgBuf))  
    
    def sendAcknowledgement(self, msgSeq, userAdrs):
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
        self.transport.write(msgBuf.raw, userAdrs)
    
    
    def sendUserList(self,userAdrs ,msgBuf = None):
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
            msgHead = (self.seqNbr[userAdrs]<<5)+ msgType 
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
        self.transport.write(msgBuf.raw,userAdrs)
        self.manageTimer(userAdrs,self.sendUserList,(userAdrs, msgBuf))    
        
        
    def sendMovieList(self,userAdrs ,msgBuf=None):
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
            msgHead = (self.seqNbr[userAdrs]<<5)+ msgType 
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
        self.transport.write(msgBuf.raw,(userAdrs))
        self.manageTimer(userAdrs, self.sendUserList,(userAdrs, msgBuf))
        

    def sendNotification(self, user, otherUser, msgBuf=None):
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
            if (user.userChatRoom  is ROOM_IDS.MAIN_ROOM):
                if(self.userState[user.userAddress] is Tools.USER_STATES.INITIALAZATION_COMPLETE):
                    msgType = 9
                else : msgType = 11
                movieId = 0
            elif(user.userChatRoom is ROOM_IDS.OUT_OF_THE_SYSTEM_ROOM):
                msgType = 10
                movieId = 1
            else :
                msgType = 12
                movieId = self.serverProxy.getMovieByTitle(user.userChatRoom).movieId
                
            msgHead = (self.seqNbr[user.userAddress]<<5)+ msgType
            msgLen  = 5 + len(user.userName)
            msgBuf  = ctypes.create_string_buffer(msgLen)
            struct.pack_into('>HHB'+str(len(user.userName))+'s',
                             msgBuf, 0, msgHead, msgLen, movieId, user.userName)
        self.transport.write(msgBuf.raw,otherUser.userAddress)  
        self.manageTimer(otherUser.userAddress,self.sendNotification,(user,otherUser, msgBuf))
          
           
  
    def sendChatMessage(self, user, chatMessage, otherUser, msgBuf=None):
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
            msgHead = (self.seqNbr[user.userAddress]<<5) + msgType
            msgLen  = 6 + len(user.userName) + len(chatMessage)
            msgBuf  = ctypes.create_string_buffer(msgLen)
            struct.pack_into('>HHH'+str(len(user.userName))+'s'+str(len(chatMessage))+'s', msgBuf,
                             0, msgHead, msgLen, len(user.userName), user.userName, chatMessage)
        self.transport.write(msgBuf.raw ,otherUser.userAddress)
        self.manageTimer(otherUser.userAddress,self.sendChatMessage,(user,chatMessage, otherUser, msgBuf))

            
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
        
    def manageTimer(self, userAdrs, sendMessage, args):
        """
        :param funcion sendMessage : the function that sends the message.
        :param string args    : the arguments of the function.
        
        called whenever  a message is sent to activate/desactivate
        the timer.The timer calls the function sendMessage after 0.5sec if
        not desactivated.
        To control the timer, his id is stored in the timers dictionary.
        """
        if(self.counter[userAdrs] < 100):
            self.counter[userAdrs] += 1
            self.timer[userAdrs]    = reactor.callLater(0.5, sendMessage, *args)
        else :
            self.counter[userAdrs] = 0
            
