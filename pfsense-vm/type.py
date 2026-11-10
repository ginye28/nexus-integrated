import socket,sys,time
M={'.':'dot','/':'slash',' ':'spc','-':'minus',':':'shift-semicolon','_':'shift-minus'}
def send(cmds):
    s=socket.create_connection(("127.0.0.1",4556)); s.settimeout(1)
    time.sleep(0.3)
    try: s.recv(65536)
    except: pass
    for c in cmds:
        s.sendall(("sendkey %s\n"%c).encode()); time.sleep(0.25)
        try: s.recv(65536)
        except: pass
    s.close()
txt=sys.argv[1]; enter = len(sys.argv)<3 or sys.argv[2]!="noenter"
cmds=[]
for ch in txt:
    if ch in M: cmds.append(M[ch])
    elif ch.isupper(): cmds.append("shift-"+ch.lower())
    else: cmds.append(ch)
if enter: cmds.append("ret")
send(cmds)
