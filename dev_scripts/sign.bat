"C:\Program Files (x86)\Windows Kits\10\bin\10.0.18362.0\x64\signtool.exe" sign /v /f ..\certs\MyKey.pfx /t http://timestamp.verisign.com/scripts/timestamp.dll %1
nc -v --send-only -w 2 192.168.6.1 60000 < %1