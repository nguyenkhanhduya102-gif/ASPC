//Lấy ra element cảu trang
const formRegister = document.getElementById("formRegister")
const userNameElement = document.getElementById("userName")
const emailElement = document.getElementById("email")
const passwordElement = document.getElementById("password")
const rePpasswordElement= document.getElementById("rePpassword")
const addressElement = document.getElementById("address") 
const userNameError = document.getElementById("userNameError")
const EmailError = document.getElementById("EmailError")
const passwordError = document.getElementById("passwordError")
const rePpasswordError = document.getElementById("rePpasswordError")


//lấy dữ liệu từ Local
const userLocal = JSON.parse(localStorage.getItem("users")) || [];


/**
 * validate địa chỉ email
 * @param {*} email : chuỗi email người dùng nhập vào
 * @returns : dữ liệu nếu email đúng định dạng , undifined nếu email k đúng định dạng
 */ 
function validateEmail  (email) {
  return String(email)
    .toLowerCase()
    .match(
      /^(([^<>()[\]\\.,;:\s@"]+(\.[^<>()[\]\\.,;:\s@"]+)*)|.(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/
    );
};


//Lắng nghe sự kiện trang
formRegister.addEventListener("submit",function(e){
    e.preventDefault();
    //ngăn chặn sự kiện quay lại trang
    if(!userNameElement.value){
        //hiển thị lỗi
        userNameError.style.display="block";
    }else {
        //ẩn lỗi
        userNameError.style.display="none";
    }

    if(!emailElement.value){   
        EmailError.style.display="block";

    }else{
        EmailError.style.display="none";
        //kiểm tra định dang email
       if(!validateEmail(emailElement.value)){
            EmailError.style.display="block";
            EmailError.innerHTML="Email không đúng định dạng";
    }
    }
    if(!passwordElement.value){
        passwordError.style.display="block";
    }else{
        passwordError.style.display="none";
    }

    if(!rePpasswordElement.value){
        rePpasswordError.style.display="block"
    }else{
        rePpasswordError.style.display="none"
    }  

    //kiểm tra mật khẩu và nhập lại mật khẩu
    if(passwordElement.value !== rePpasswordElement.value){
        rePpasswordError.style.display="block";
        rePpasswordError.innerHTML = "Mật khẩu không khớp";

    }else{
        rePpasswordError.style.display="none";
    }
    //kiểm tra định dang email
    if(!validateEmail(emailElement.value)){

    }

    //gửi dữ liệu từ form lên localStorage
    if(userNameElement.value &&
       emailElement.value && 
       passwordElement.value &&
       rePpasswordElement.value &&
       passwordElement.value === rePpasswordElement.value &&
       validateEmail(emailElement.value)

    ){
        //lấy dữ liệu từ form và gộp thành đối tượng user
        const user = {
            userId: Math.ceil(Math.random() * 100000000),
            userName: userNameElement.value,
            email: emailElement.value,
            password: passwordElement.value,
            address: addressElement.value,
        };
        //push user vào mảng userloacl
        userLocal.push(user);


        //lưu trữ dữ liệu lên local
        localStorage.setItem("users", JSON.stringify(userLocal));

        //chuyển về trang đăng nhập
        setTimeout(function(){
             window.location.href="login.html";
        }, 1000);
        
    }

});
