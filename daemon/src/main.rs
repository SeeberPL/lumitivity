use std::net::UdpSocket; //For networking
use rdev::{listen, EventType}; //For keyboard/Mouse inputs

struct InputRelay {
    socket: UdpSocket,
    target_addr: String,
}

impl InputRelay {
    fn new(ip: &str) -> Self {
        let sock = UdpSocket::bind("0.0.0.0:0").expect("Failed to bind socket");
        
        Self {
            socket: sock,
            target_addr: ip.to_string(),
        }
    }

    fn run(&self) {
        let socket = self.socket.try_clone().expect("Failed to clone socket");
        let target = self.target_addr.clone();

        println!("Listening for keyboard hits... (Press Ctrl+C to stop)");

        listen(move |event| {
            match event.event_type {
                EventType::KeyPress(_) => {
                    // Send the 'k' byte to the Pi
                    socket.send_to(b"k", &target).expect("Failed to send UDP Packet");
                    println!("KeyboardHit");
                },
                EventType::ButtonPress(_) => {
                    // Send the 'k' byte to the Pi
                    socket.send_to(b"k", &target).expect("Failed to send UDP Packet");
                    println!("MouseClick");
                },
                _ => {} //Ignore Mouse Moves and Key releases
            }
        }).expect("Could not start keyboard listener");
    }
}


fn main() {
    let relay = InputRelay::new("192.168.4.35:8080");
    println!("Relay object created for: {}", relay.target_addr);
    relay.run();
}