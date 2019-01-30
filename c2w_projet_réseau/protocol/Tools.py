#!/usr/bin/env python
import struct
import ctypes


class USER_STATES(object):
    class INITIALAZATION_COMPLETE(object):
        pass

    class LOGIN_OK_PENDING(object):
        pass

    class USER_LIST_PENDING(object):
        pass

    class MOVIE_LIST_PENDING(object):
        pass
    
    class CORRECT_USERNAME_PENDING(object):
        pass
    
    class IN_ROOM(object):
        pass

    class CONNECTING(object):
        pass

    class MOVIE_ROOM(object):
        pass

    class DISCONNECTED(object):
        pass

    class TO_ROOM_REQUEST_PENDING(object):
        pass

    class TO_OUT_OF_THE_SYSTEM_ROOM_REQUEST_PENDING(object):
        pass
    
    class MOVIE_LIST_RECIEVED(object):
        pass
    
    class USER_LIST_RECIEVED(object):
        pass  

def getData(dataGram,msgLen):
    """
    :param string datagram: the payload of the UDP packet.
    :param int msgLen: the length of the datagram received.

    This function extract the data field from the datagram.
    """
    f=struct.unpack_from('!I'+str(msgLen-4)+'s',dataGram,0)
    return f[1]
    
def getRoomIdFromData(dataGram,msgLen):
    """
    :param string datagram: the payload of the UDP packet.
    :param int msgLen: the length of the datagram received.

    This function extracts the roomId field from the packet.    
    """
    f=struct.unpack_from('!IB',dataGram,0)
    return f[1]


def getHead(dataGram):
    """
    :param string datagram: the payload of the UDP packet.

    This function extract the header of the packet (sequence Number-Type).    
    """
    f = struct.unpack_from('!H',dataGram,0)
    seqNbr  =  f[0]>>5
    msgType =  f[0]&31
    return (seqNbr, msgType)
    
def getLen(dataGram):
    """
    :param string datagram: the payload of the UDP packet.

    This function extract the msgLength field from the packet.    
    """
    f = struct.unpack_from('!HH',dataGram,0)
    return f[1]

