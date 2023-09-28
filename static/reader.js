function onScanSuccess(decodedText, decodedResult) {
  // handle the scanned code as you like, for example:
  // console.log(`Code matched = ${decodedText}`, decodedResult);
  let decoded = decodedText;
  // document.getElementById("res").innerHTML = url;
  html5QrCode.stop().then((ignore) => {
    Swal.fire({
      title: "Mohon tunggu sebentar!",
      text: "Sampahmu sedang di-scan...",
      didOpen: () => {
        Swal.showLoading();
      },
    });

    if (
      decoded.includes("http://") ||
      decoded.includes("https://") ||
      decoded.includes("www.")
    ) {
      Swal.fire({
        icon: "error",
        title: "Oops...",
        didOpen: () => {
          Swal.hideLoading();
        },
        text: "Mohon maaf, Sepertinya anda salah scan QR Code, silakan scan QR Code yang ada di tempat sampah!",
      }).then((result) => {
        if (result.isConfirmed) {
          window.location.href = "/scan";
        } else if (result.isDismissed) {
          window.location.href = "/scan";
        }
      });
      return;
    }

    if (
      !decoded.startsWith("sd") &&
      !decoded.startsWith("smp") &&
      !decoded.startsWith("sma") &&
      !decoded.startsWith("smk") &&
      !decoded.startsWith("univ") &&
      !decoded.startsWith("lp")
    ) {
      Swal.fire({
        icon: "error",
        title: "Oops...",
        text: "Mohon maaf, Sepertinya anda salah scan QR Code, silakan scan QR Code yang ada di tempat sampah!",
        didOpen: () => {
          Swal.hideLoading();
        },
      }).then((result) => {
        if (result.isConfirmed) {
          window.location.href = "/scan";
        } else if (result.isDismissed) {
          window.location.href = "/scan";
        }
      });
      return;
    }

    fetch("/scan", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        topic: decoded,
      }),
    })
      .then((response) => {
        return response.json();
      })
      .then((data) => {
        if (data.status_code == 1) {
          Swal.fire({
            icon: "success",
            title: "Voila...",
            html: `Sampahmu berhasil di-scan!<br> Anda baru saja menyelamatkan bumi dengan membuang ${data.bottle} Botol, <br>${data.new_point} Poin ditambahkan ke dompet mu!`,
            backdrop: `
                rgba(0,0,123,0.4)
                url("/static/img/minions.gif")
                left top
                no-repeat
              `,
            confirmButtonText: "Lihat Dompet",
            cancelButtonText: "Scan Lagi",
            showCancelButton: true,
          }).then((result) => {
            if (result.isConfirmed) {
              window.location.href = "/profil";
            } else if (result.isDismissed) {
              window.location.href = "/scan";
            } else {
              window.location.href = "/profil";
            }
          });
        } else if (data.status_code == 2) {
          Swal.fire({
            icon: "error",
            title: "Oops...",
            text: "Mohon maaf, sepertinya yang kamu masukkan bukan botol",
          }).then((result) => {
            if (result.isConfirmed) {
              window.location.href = "/scan";
            } else if (result.isDismissed) {
              window.location.href = "/scan";
            }
          });
        } else {
          Swal.fire({
            icon: "error",
            title: "Oops...",
            html:
              "Sampahmu gagal di-scan!<br>" + data.message ||
              "Mohon maaf, terjadi kesalahan pada server kami!, silakan coba lagi nanti!",
          }).then((result) => {
            if (result.isConfirmed) {
              window.location.href = "/scan";
            } else if (result.isDismissed) {
              window.location.href = "/scan";
            }
          });
        }
      })
      .catch((err) => {
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: "Sampahmu gagal di-scan!",
        }).then((result) => {
          if (result.isConfirmed) {
            window.location.href = "/scan";
          } else if (result.isDismissed) {
            window.location.href = "/scan";
          }
        });
      });
  });
}

const config = {
  fps: 10,
  qrbox: {
    width: 250,
    height: 250,
  },
};
const html5QrCode = new Html5Qrcode("reader");

let error = "";
html5QrCode
  .start({ facingMode: { exact: "environment" } }, config, onScanSuccess)
  .catch((err) => {
    // Start failed, handle it.
    Swal.fire({
      icon: "error",
      title: "Oops...",
      text: "Silakan scan QR Code melalui ponsel anda!",
    }).then((result) => {
      if (result.isConfirmed) {
        window.location.href = "/";
      } else if (result.isDismissed) {
        window.location.href = "/";
      }
    });
    error = err;
  })
  .finally(() => {
    if (error == "") {
      Swal.close();
    }
  });

Swal.fire({
  title: "Mohon tunggu sebentar!",
  text: "Sedang berusaha membuka kamera...",

  didOpen: () => {
    Swal.showLoading();
  },
});

// document.getElementById('reader').
