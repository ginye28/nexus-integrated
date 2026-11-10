import socket,sys,time,re
def conn(): 
    s=socket.create_connection(("127.0.0.1",4555)); s.settimeout(0.5); return s
def read(s,secs):
    end=time.time()+secs; buf=b""
    while time.time()<end:
        try:
            d=s.recv(65536)
            if not d: break
            buf+=d
        except socket.timeout: pass
    return buf.decode("utf-8","replace")
if __name__=="__main__":
    s=conn(); out=read(s,float(sys.argv[1]))
    out=re.sub(r'\x1b\[[0-9;?]*[A-Za-z]','',out)
    print(out[-3000:])
