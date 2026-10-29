#pragma once
#include "protocol.h"
#include <array>
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <fcntl.h>
#include <unistd.h>
#endif

namespace mpvr {
class Receiver {
#ifdef _WIN32
    SOCKET socket_=INVALID_SOCKET;
    bool winsock_=false;
#else
    int socket_=-1;
#endif
public:
    std::array<State,2> hands{};
    Control control;
    Receiver()=default;
    Receiver(const Receiver&)=delete;
    Receiver& operator=(const Receiver&)=delete;
    ~Receiver() { close(); }
    unsigned short port() const {
        sockaddr_in address{};
#ifdef _WIN32
        int length=sizeof(address);
#else
        socklen_t length=sizeof(address);
#endif
        if (getsockname(socket_,reinterpret_cast<sockaddr*>(&address),&length)!=0) return 0;
        return ntohs(address.sin_port);
    }
    bool open(unsigned short port=39570) {
#ifdef _WIN32
        WSADATA data{};
        if (WSAStartup(MAKEWORD(2,2),&data)!=0) return false;
        winsock_=true;
#endif
        socket_=::socket(AF_INET,SOCK_DGRAM,0);
#ifdef _WIN32
        if (socket_==INVALID_SOCKET) { close(); return false; }
#else
        if (socket_<0) return false;
#endif
        sockaddr_in address{}; address.sin_family=AF_INET; address.sin_port=htons(port); address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
        if (::bind(socket_,reinterpret_cast<sockaddr*>(&address),sizeof(address))!=0) { close(); return false; }
#ifdef _WIN32
        u_long mode=1;
        if (ioctlsocket(socket_,FIONBIO,&mode)!=0) { close(); return false; }
#else
        if (fcntl(socket_,F_SETFL,O_NONBLOCK)<0) { close(); return false; }
#endif
        return true;
    }
    void close() {
#ifdef _WIN32
        if (socket_!=INVALID_SOCKET) closesocket(socket_);
        socket_=INVALID_SOCKET;
        if (winsock_) WSACleanup();
        winsock_=false;
#else
        if (socket_>=0) ::close(socket_);
        socket_=-1;
#endif
        hands={}; control={};
    }
    void poll(double now, bool hmd_valid) {
        // Sem threads soltas; processamento limitado por RunFrame.
        for (unsigned count=0;count<32;++count) {
            unsigned char buffer[1024]{}; sockaddr_in peer{};
#ifdef _WIN32
            int length=sizeof(peer);
            const int size=recvfrom(socket_,reinterpret_cast<char*>(buffer),sizeof(buffer),0,reinterpret_cast<sockaddr*>(&peer),&length);
#else
            socklen_t length=sizeof(peer);
            const auto size=recvfrom(socket_,buffer,sizeof(buffer),0,reinterpret_cast<sockaddr*>(&peer),&length);
#endif
            if (size<0) break;
            Frame frame;
            if (decode(buffer,static_cast<std::size_t>(size),frame)) { hands[frame.side].accept(frame,now); continue; }
            if (size!=16 || std::memcmp(buffer,"MPVRC001",8)!=0) continue;
            const auto command=u32(buffer+8), value=u32(buffer+12);
            if (command==1) control.pulse(now,value);
            if (command==2 && value==0) {
                unsigned char response[20]; std::memcpy(response,"MPVRA001",8);
                put32(response+8,1); put32(response+12,(hands[0].live(now)?1u:0u)|(hands[1].live(now)?2u:0u)); put32(response+16,hmd_valid?1u:0u);
                sendto(socket_,reinterpret_cast<const char*>(response),sizeof(response),0,reinterpret_cast<const sockaddr*>(&peer),length);
            }
        }
    }
};
} // namespace mpvr
