#include "../src/receiver.h"
#include "test_helpers.h"
#include <iostream>
int main() {
    mpvr::Receiver receiver;check(receiver.open(0),"open loopback");
    const auto port=receiver.port();check(port!=0,"ephemeral port");
    mpvr::Receiver collision;check(!collision.open(port),"port collision detected");
    const auto sender=::socket(AF_INET,SOCK_DGRAM,0);
    sockaddr_in target{};target.sin_family=AF_INET;target.sin_addr.s_addr=htonl(INADDR_LOOPBACK);target.sin_port=htons(port);
    const auto send=[&](const unsigned char* data,std::size_t size) {
        check(sendto(sender,reinterpret_cast<const char*>(data),static_cast<int>(size),0,
            reinterpret_cast<sockaddr*>(&target),sizeof(target))==static_cast<int>(size),"UDP send");
    };
    auto bytes=packet(1,1);send(bytes.data(),bytes.size());receiver.poll(1,true);
    check(receiver.hands[1].live(1) && !receiver.hands[0].live(1),"real datagram accepted for right hand");
    unsigned char command[16]{};std::memcpy(command,"MPVRC001",8);mpvr::put32(command+8,1);mpvr::put32(command+12,300);
    send(command,16);receiver.poll(1.1,true);
    check(receiver.control.pressed(1.2,true),"calibration pulse accepted");
    check(!receiver.control.pressed(1.401,true),"release works without new datagrams");
    mpvr::put32(command+8,2);mpvr::put32(command+12,0);send(command,16);receiver.poll(1.2,true);
    unsigned char response[64]{};
    check(recv(sender,reinterpret_cast<char*>(response),sizeof(response),0)==20,"status response");
    check(std::memcmp(response,"MPVRA001",8)==0 && mpvr::u32(response+8)==1 && mpvr::u32(response+12)==2 && mpvr::u32(response+16)==1,"status protocol/hands/HMD");
    const std::array<float,12> head={1,0,0,0,0,1,0,1.7f,0,0,1,0};
    mpvr::put32(command+8,3);send(command,16);receiver.poll(1.21,true,head);
    check(recv(sender,reinterpret_cast<char*>(response),sizeof(response),0)==60,"head pose response");
    check(std::memcmp(response,"MPVRP001",8)==0 && mpvr::u32(response+8)==1 && std::abs(mpvr::number(response+40)-1.7f)<.001f,"actual HMD matrix exposed");
    bytes=packet(1,2,false);send(bytes.data(),bytes.size());receiver.poll(1.3,true);
    check(!receiver.hands[1].live(1.3),"loss deactivates recipient");
    for (unsigned side=0;side<2;++side) {
        bytes=packet(side,3);send(bytes.data(),bytes.size());
    }
    receiver.poll(1.4,true);
    mpvr::put32(command+8,2);send(command,16);receiver.poll(1.41,true);
    check(recv(sender,reinterpret_cast<char*>(response),sizeof(response),0)==20,"both hands status response");
    check(mpvr::u32(response+12)==3,"simultaneous valid hands reported as mask three");
    send(command,16);receiver.poll(1.91,true);
    check(recv(sender,reinterpret_cast<char*>(response),sizeof(response),0)==20,"expired hands status response");
    check(mpvr::u32(response+12)==0,"status reports zero after half-second expiry without changing last frames");
#ifdef _WIN32
    closesocket(sender);
#else
    ::close(sender);
#endif
    receiver.close();receiver.close();check(!receiver.hands[1].received,"idempotent cleanup");
    std::cout<<"UDP, handshake, control, missing hand and cleanup passed\n";
}
