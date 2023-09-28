$(document).ready(function () {
  const video = document.getElementById("video");
  const canvas = document.getElementById("canvas");
  const context = canvas.getContext("2d");

  // Get the camera feed
  navigator.mediaDevices
    .getUserMedia({ video: { facingMode: "environment" } })
    .then(function (stream) {
      video.srcObject = stream;
    })
    .catch(function (error) {
      console.error("Error accessing camera:", error);
    });

  // When the video is playing, start scanning for QR codes
  video.addEventListener("play", function () {
    const width = video.videoWidth;
    const height = video.videoHeight;

    canvas.width = width;
    canvas.height = height;

    function scanQRCode() {
      context.drawImage(video, 0, 0, width, height);
      const imageData = context.getImageData(0, 0, width, height);
      const qrCodes = jsQR(imageData.data, imageData.width, imageData.height);

      if (qrCodes && qrCodes.length > 0) {
        const qrData = qrCodes[0].data;
        console.log("QR Code Data:", qrData);

        // Here, you can send the QR code data to the server using AJAX if needed
      }

      requestAnimationFrame(scanQRCode);
    }

    scanQRCode();
  });
});
