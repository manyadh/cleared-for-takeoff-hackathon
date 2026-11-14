"""'Regional command' - run on a second laptop:  python -m muster.receiver 9999"""
import socket, sys
from datetime import datetime

port = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("0.0.0.0", port))
print(f"REGIONAL COMMAND listening on :{port}\n")
COLORS = {"R": "\033[41m", "O": "\033[43m", "Y": "\033[103m", "G": "\033[42m"}
while True:
    data, addr = s.recvfrom(512)
    line = data.decode("ascii", "ignore")
    f = line.split("|")
    c = COLORS.get(f[2] if len(f) > 2 else "", "")
    print(f"{datetime.now():%H:%M:%S} {c} {f[2] if len(f)>2 else '?'} \033[0m {line}   ({len(data)} bytes)")
