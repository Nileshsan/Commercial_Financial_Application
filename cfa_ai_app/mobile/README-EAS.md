EAS build (APK) quick guide

1) Ensure the `API_URL` in `.env` points to the backend you want the app to talk to (for local laptop backend use the laptop LAN IP). Example:

API_URL=http://192.168.1.12:8000/api/

2) Install EAS CLI and login:

npm install -g eas-cli
eas login

3) Start a production APK build (cloud):

eas build --platform android --profile production

4) When build completes, download the APK URL and install on your phone or emulator.

5) If you want the phone to use your laptop backend, ensure the phone is on the same Wi-Fi and the backend is reachable at the IP in `.env`.
