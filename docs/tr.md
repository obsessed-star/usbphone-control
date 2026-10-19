# Türkçe başlangıç

Bu proje USB kablosuyla bağlanan Android telefonu Python, terminal veya MCP üzerinden kontrol eden ayrı bir araçtır. AI modeli gerektirmez. Agent kısmı ayrı `graphpilot-agent` deposundadır.

1. Android'in resmi Platform Tools paketini kurun.
2. Telefonda geliştirici seçeneklerinden USB hata ayıklamayı açın.
3. Veri aktarabilen USB kablosunu bağlayın ve bilgisayar için çıkan RSA iznini telefondan onaylayın.
4. `python -m pip install -e .` komutuyla paketi kurun.
5. `python -m usbphone.cli devices` ile cihazı görün.
6. `python -m usbphone.cli observe` ile ekran görüntüsü ve arayüz öğelerini alın.

Her görüntü bir `observation_id` üretir. Dokunma, kaydırma, yazma, tuş veya uygulama açma işlemi bu kimlikle çağrılır. Kimlik 30 saniye sonra geçersizdir ve yalnızca bir işlemde kullanılabilir. Her işlemden sonra yeni ekran alınır.

İlk sürümde standart ADB metin girişi nedeniyle Türkçe karakterler yazdırılamaz; bu tür giriş açıkça reddedilir. Telefonun kendi klavyesini kullanın. XML'de parola olarak işaretlenen öğeler atlanır fakat ekran görüntüsü kişisel bilgi içerebilir; gerçek ekranları GitHub'a yüklemeyin.
