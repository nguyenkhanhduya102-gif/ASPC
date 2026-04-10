@echo off
color 0A
title Khởi động Hệ thống ASPC

echo ==================================================
echo      KHOI DONG HE THONG ASPC (MAIN + VISION AI)
echo ==================================================

echo [1] Dang khoi dong ASPC Main Server (Port 5000)...
start "ASPC Main Server" cmd /c "python app.py"

:: Đợi 3 giây cho server lên hẳn
timeout /t 3 /nobreak >nul

echo [2] Dang khoi dong ASPC Vision AI (Port 5001)...
start "ASPC Vision AI" cmd /c "python yolo_stream.py"

:: Đợi thêm 2 giây rồi tự động gọi trình duyệt mở trang web
timeout /t 2 /nobreak >nul
echo [3] Tu dong mo trinh duyet Web...
start http://127.0.0.1:5000

echo.
echo HOAN TAT! He thong da san sang.
pause