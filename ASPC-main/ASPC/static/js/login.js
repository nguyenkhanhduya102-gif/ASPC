//element của trang
const formLogin = document.getElementById("formLogin");
const emailElement = document.getElementById("email")
const passwordElement = document.getElementById("password")
const alertError = document.getElementById("alertError")
//lắng nghe sự kiện submit form đăng nhập tài khoản
formLogin.addEventListener("submit" , function(e){
    // ngăn chặn sự kiện load lại trang
    e.preventDefault(); 
    
    // BỔ SUNG: Kiểm tra dữ liệu trống
    if (!emailElement.value || !passwordElement.value) {
        alert("Vui lòng nhập đầy đủ Email và Mật khẩu.");
        return;
    }

    // lấy dữ liệu từ local về
    const userLocal = JSON.parse(localStorage.getItem("users")) || [];
    
    // tìm kiếm email và mật khẩu mà người dùng nhập vào có tồn tại trên local
    const findUser = userLocal.find(
        (user) => 
        user.email === emailElement.value.trim() && 
        user.password === passwordElement.value.trim()
    );
    
    // Xử lý kết quả đăng nhập
    if (!findUser){
        // Thông báo lỗi chung chung (an toàn hơn)
        alertError.style.display = "block";
    } else {
        // BỔ SUNG QUAN TRỌNG: Lưu ID người dùng vào LocalStorage
        localStorage.setItem('user_id', findUser.userId);
    
    // Lưu một device_id mặc định (nếu bạn chưa có logic chọn thiết bị)
   
        // Thay vì lưu 'device_default', hãy lưu đúng mã mà server đang nhận mặc định
        calStorage.setItem('device_id', 'ESP32_DEFAULT'); // Tạm thời để mặc định, sau này có thể là ESP32_001
        

        
        
        // Chuyển về trang chủ
        window.location.href="index.html";
    }
});