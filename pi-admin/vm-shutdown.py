#!/usr/bin/python3
import socket,json,time,os
path='/var/lib/browser-vault-vm/qmp.sock'
with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
    s.settimeout(5); s.connect(path)
    stream=s.makefile('rwb',buffering=0)
    stream.readline()
    for command in ('qmp_capabilities','system_powerdown'):
        stream.write((json.dumps({'execute':command})+'\n').encode())
        while True:
            result=json.loads(stream.readline())
            if 'return' in result:break
            if 'error' in result:raise RuntimeError(result['error'])
    # Keep ExecStop active until QEMU exits; systemd then has no VM to kill.
    s.settimeout(220)
    try:
        while stream.readline(): pass
    except (TimeoutError,OSError):pass
