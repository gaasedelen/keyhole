echo *******************************************************
echo *** PLEASE RUN THIS UNDER A VS 2019 COMMAND PROMPT! ***
echo *******************************************************

REM create cert materials directory and change to it...
mkdir ..\certs
pushd ..\certs

REM generate new code signing certs
MakeCert /n "CN=TestCert" /r /h 0 /eku "1.3.6.1.5.5.7.3.3,1.3.6.1.4.1.311.10.3.13" /e 01/01/2021 /sv MyKey.pvk MyCert.cer
Pvk2Pfx /pvk MyKey.pvk /spc MyCert.cer /pfx MyKey.pfx

REM restore to cwd...
popd