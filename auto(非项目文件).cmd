@echo off
set /p msg=remarks:
git add .
git commit -m "%msg%"
git push origin main
echo OK!!!!
pause