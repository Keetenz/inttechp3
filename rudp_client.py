#!/usr/bin/env python3
"""
rudp_client.py — STUDENT SKELETON
Goal: Implement a minimal "Reliable UDP" (RUDP) client over UDP (stop-and-wait)
that streams a World Cup match, one event per packet, to the scoreboard server.

YOU MUST IMPLEMENT:
  1) 3-way handshake:  (you send) SYN(seq=x) -> (expect) SYN-ACK(ack=x+1) -> (you send) ACK(seq=x+1, ack=y+1)
     - x is YOUR random initial sequence number (ISN); y is the server's
  2) DATA send loop (stop-and-wait):
       - send each line of the match feed as one DATA packet
       - sequence numbers count BYTES: the next seq = this seq + len(payload)
       - wait for an ACK whose ack number == seq + len(payload)
       - if timeout or wrong ACK: retransmit (up to RETRIES = 5 tries, then give up)
  3) Teardown: (you send) FIN -> (expect) FIN-ACK(ack = FIN's seq + 1)

Usage:  python3 rudp_client.py [match_feed.txt]
"""
import random, socket, struct, sys, time

# ===================== CONFIG (EDIT HOST/PORT) =====================
SERVER_HOST = '127.0.0.1'      # server IP or hostname
ASSIGNED_PORT = 30077   # <-- REPLACE with your assigned UDP port (from Canvas)
SERVER = (SERVER_HOST, ASSIGNED_PORT)
# ==================================================================

# Timing/reliability parameters
RTO = 0.5          # retransmission timeout (seconds)
RETRIES = 5        # max tries per packet

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
    print(f'[CLIENT] {direction} seq={seq} ack={ack} flags={flag_str(flags)} len={length}' + (f'  ({note})' if note else ''))

def send_recv_with_retry(sock, pkt, is_expected):
    """
    Utility: send a packet and wait up to RTO for a reply that passes is_expected(seq, ack, flags, payload).
    Replies that fail the check are logged and ignored WITHOUT restarting the timer.
    Retries up to RETRIES times. Returns (seq, ack, flags, payload) on success, None on failure.
    """
    seq, ack, flags, ln = struct.unpack(HDR, pkt[:HDR_SZ])
    for attempt in range(1, RETRIES + 1):
        sock.sendto(pkt, SERVER)
        log('SEND', seq, ack, flags, ln, f'try {attempt}/{RETRIES}' if attempt > 1 else '')
        deadline = time.monotonic() + RTO
        while (left := deadline - time.monotonic()) > 0:
            sock.settimeout(left)
            try:
                resp, _ = sock.recvfrom(2048)
            except socket.timeout:
                break
            msg = unpack_msg(resp)
            if msg is None:
                continue
            if is_expected(*msg):
                log('RECV', msg[0], msg[1], msg[2], len(msg[3]))
                return msg
            log('RECV', msg[0], msg[1], msg[2], len(msg[3]), 'stale/unexpected, ignored')
        print(f'[CLIENT] TIMEOUT after {RTO}s')
    return None

def main():
    feed_path = sys.argv[1] if len(sys.argv) > 1 else 'match_feed.txt'
    with open(feed_path) as f:
        events = [line.rstrip('\n') for line in f if line.strip()]

    cli = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # ============ PHASE 1: HANDSHAKE (YOU IMPLEMENT) ==============
    # TODO:
    #   - pick x = random.randint(0, SEQ_MOD - 1) and print it
    #   - send SYN: seq = x, ack = 0, flags = SYN
    #   - wait (with retry) for a SYN-ACK whose ack == x + 1
    #   - on success: y = the SYN-ACK's seq; print it
    #   - send the final ACK: seq = x + 1, ack = y + 1, flags = ACK (log it!)
    #   - print('[CLIENT] Connection established')
    #   - if no valid SYN-ACK after RETRIES tries: print a message and exit
    # HINT: send_recv_with_retry() takes a function that decides whether a reply is the
    #       one you are waiting for, e.g.  lambda s, a, fl, p: fl == SYN | ACK and a == seq_add(x, 1)
    pass  # <-- replace with your handshake code
    # ===============================================================

    # ============ PHASE 2: DATA SEND LOOP (YOU IMPLEMENT) =========
    # TODO:
    #   - the first DATA seq is x + 1; every DATA carries ack = y + 1 and flags = ACK
    #   - for each event in events:
    #       * payload = event.encode()
    #       * send DATA and wait (with retry) for an ACK with ack == seq + len(payload)
    #       * on success: seq = seq + len(payload)
    #       * on failure: print a message and exit
    pass  # <-- replace with your data send loop
    # ===============================================================

    # ============ PHASE 3: TEARDOWN (YOU IMPLEMENT) ===============
    # TODO:
    #   - send FIN: seq = your current seq, ack = y + 1, flags = FIN
    #   - wait (with retry) for a FIN-ACK whose ack == your seq + 1
    #   - on success print('[CLIENT] Connection closed')
    pass  # <-- replace with your teardown code
    # ===============================================================

    cli.close()

if __name__ == '__main__':
    main()
