#!/usr/bin/env python3
"""
rudp_server.py — STUDENT SKELETON
Goal: Implement a minimal "Reliable UDP" (RUDP) server over UDP that keeps
the live scoreboard for a World Cup match.

YOU MUST IMPLEMENT:
  1) 3-way handshake:  SYN(seq=x) -> (you send) SYN-ACK(seq=y, ack=x+1) -> (expect) ACK(ack=y+1)
     - y is YOUR random initial sequence number (ISN)
  2) DATA handling with byte sequence numbers + an ACK for every DATA
     - maintain 'expect_seq' (the next in-order byte you expect)
     - deliver ONLY in-order data to the scoreboard; a duplicate must NOT be delivered
       (a duplicated GOAL changes the score!)
     - always reply with ack = expect_seq
  3) Teardown: (expect) FIN -> (you send) FIN-ACK(ack = FIN's seq + 1)

Usage:  python3 rudp_server.py [seed]
Tips:
  - Use the provided log() for EVERY packet you send or receive.
  - Send every reply with send_unreliable() so the network can drop or delay it.
  - Keep the server single-client and single-threaded for simplicity.
"""
import random, socket, struct, sys, threading

# ===================== CONFIG (EDIT YOUR PORT) =====================
ASSIGNED_PORT = 30009  # <-- REPLACE with your assigned UDP port (from Canvas)
# ==================================================================

# --- Flag bits (1 byte) ---
SYN, ACK, FIN = 0x01, 0x02, 0x04

# Header format: seq(4B) | ack(4B) | flags(1B) | len(2B)  -> 11 bytes, inside the UDP payload
HDR = '!I I B H'
HDR_SZ = struct.calcsize(HDR)
SEQ_MOD = 2 ** 32

def seq_add(a: int, n: int) -> int:
    """Sequence-number arithmetic wraps around at 2^32, just like TCP."""
    return (a + n) % SEQ_MOD

def pack_msg(seq: int, ack: int, flags: int, payload: bytes = b'') -> bytes:
    if isinstance(payload, str):
        payload = payload.encode()
    return struct.pack(HDR, seq, ack, flags, len(payload)) + payload

def unpack_msg(pkt: bytes):
    if len(pkt) < HDR_SZ:
        return None
    seq, ack, flags, ln = struct.unpack(HDR, pkt[:HDR_SZ])
    return seq, ack, flags, pkt[HDR_SZ:HDR_SZ + ln]

def flag_str(flags: int) -> str:
    names = [n for bit, n in ((SYN, 'SYN'), (FIN, 'FIN'), (ACK, 'ACK')) if flags & bit]
    return '|'.join(names) or 'NONE'

def log(direction: str, seq: int, ack: int, flags: int, length: int, note: str = ''):
    """Required log format. Wireshark cannot decode our header, so these lines are the record."""
    print(f'[SERVER] {direction} seq={seq} ack={ack} flags={flag_str(flags)} len={length}' + (f'  ({note})' if note else ''))

# ============ SIMULATED UNRELIABLE NETWORK (PROVIDED — DO NOT EDIT) ============
DROP_PROB = 0.10          # chance a reply is silently dropped
DELAY_PROB = 0.20         # chance a reply is held back ("VAR review")
DELAY_MS = (100, 1000)    # how long a held-back reply waits
net_rng = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else None)

def send_unreliable(sock, pkt, addr):
    """Send a reply through a network that sometimes drops or delays it."""
    r = net_rng.random()
    if r < DROP_PROB:
        print('[NET] reply dropped')
        return
    if r < DROP_PROB + DELAY_PROB:
        d = net_rng.randint(*DELAY_MS)
        print(f'[NET] reply delayed {d} ms (VAR review)')
        threading.Timer(d / 1000.0, sock.sendto, (pkt, addr)).start()
        return
    sock.sendto(pkt, addr)

# ============ SCOREBOARD (PROVIDED — DO NOT EDIT) ============
class Scoreboard:
    """Applies match events in the order delivered. A duplicated GOAL changes the score."""
    def __init__(self):
        self.score = {}
        self.events = []

    def apply(self, line: str):
        self.events.append(line)
        parts = line.split()
        if len(parts) >= 4 and parts[1] == 'KICKOFF':
            self.score = {parts[2]: 0, parts[4]: 0}
        elif len(parts) >= 3 and parts[1] == 'GOAL':
            self.score[parts[2]] = self.score.get(parts[2], 0) + 1
        print(f'[MATCH] {line}' + (f'   >>> {self.board()}' if 'GOAL' in parts[1:2] else ''))

    def board(self) -> str:
        return '  '.join(f'{t} {g}' for t, g in self.score.items())

    def save(self, path='received_feed.txt'):
        with open(path, 'w') as f:
            f.write('\n'.join(self.events) + '\n')
        print(f'[MATCH] FINAL SCORE: {self.board()}   (events saved to {path})')
# ============================================================

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', ASSIGNED_PORT))
    print(f'[SERVER] Listening on 0.0.0.0:{ASSIGNED_PORT} (UDP)')

    state = 'LISTEN'          # LISTEN -> SYN_RCVD -> ESTABLISHED -> (FIN) -> LISTEN
    client_addr = None
    client_isn = None         # x, chosen by the client
    server_isn = None         # y, chosen by you
    expect_seq = None         # next in-order byte expected from the client
    board = None              # Scoreboard(), created once the connection is established
    last_close = None         # (addr, FIN-ACK packet) so a retransmitted FIN still gets answered

    while True:
        pkt, addr = sock.recvfrom(2048)
        msg = unpack_msg(pkt)
        if msg is None:
            continue
        seq, ack, flags, pl = msg
        if flags == SYN:
          client_isn = seq #x
          client_addr = addr
          break

    server_isn = random.randint(0, SEQ_MOD - 1) #y
    state = 'SYN_RCVD'

    syn_ack_pkt = pack_msg(server_isn, seq_add(client_isn, 1), SYN | ACK)
    send_unreliable(sock, syn_ack_pkt, client_addr)

    while True:
      pkt, addr = sock.recvfrom(2048)
      msg = unpack_msg(pkt)
      if msg is None:
        continue
      if addr != client_addr:    #ignores packets from the wrong clients
        continue
        
      seq, ack, flags, pl = msg
      
      if flags == SYN:      #duplicate SYN, syn-ack was lost or delayed so we retransmit
        send_unreliable(sock, syn_ack_pkt, client_addr)
      
      elif (flags & ACK) and ack == seq_add(server_isn, 1) and seq == seq_add(client_isn, 1):    #uses bitwise & to check to specifically check bit corresponding to ACK, catches ack and hanging syn|ack
        break

    state = 'ESTABLISHED'
    expect_seq = seq_add(client_isn, 1)
    board = Scoreboard()
    print('[SERVER] Connection established')

    if pl:      #Ensures first packet is still captured even if first ACK was lost
      board.apply(pl.decode())
      expect_seq = seq_add(expect_seq, len(pl))

    while True:
      pkt, addr = sock.recvfrom(2048)
      msg = unpack_msg(pkt)
      if msg is None:
        continue
      if addr != client_addr:    #ignores packets from the wrong clients
        continue
        
      seq, ack, flags, pl = msg

      if (flags & DATA) and len(pl) > 0:
        if seq == expect_seq:
          board.apply(pl.decode())
          expect_seq = seq_add(expect_seq, len(pl))
        else:
          print("[SERVER] Duplicate or out-of-order packet received")
          
        ack_pkt = pack_msg(seq_add(server_isn, 1), expect_seq, ACK)
        send_unreliable(sock, ack_pkt, client_addr)


      
      #teardown
      elif (flags & FIN) and seq == expect_seq:
        fin_ack_pkt = pack_msg(seq_add(server_isn, 1), seq_add(seq, 1), FIN | ACK)
        send_unreliable(sock, fin_ack_pkt, client_addr)
        board.save()
        print('[SERVER] Connection closed')
        
        last_close = (client_addr, fin_ack_pkt)  #saves last_close if client sends duplicate fin
        break
  

if __name__ == '__main__':
    main()
