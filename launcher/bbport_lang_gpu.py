# SPDX-License-Identifier: GPL-2.0-or-later
"""The texts of a graphics card Windows has and Vulkan does not see (scripts/vulkan_check.py's 'unseen': the
Play page's line, the question before PLAY, Help's topic), in every language besides English. Keyed by the
English text like bbport_lang; merged into its tables on import."""
import bbport_lang

KEYS = [
    'Windows has {0}, but its Vulkan driver does not answer, so the game runs on {1}, much slower. Install the '
    'driver for {0} anew (clean installation), then restart the PC.',
    'Windows has {0}, but its Vulkan driver does not answer. Install the driver for {0} anew (clean installation), '
    'then restart the PC.',
    '{} is not used: its Vulkan driver does not answer (Help)',
    # Help's topic
    'The game does not use your graphics card',
    "Windows has the card, but its Vulkan driver does not answer or is too old for the port: the game then runs on "
    "the processor's graphics, much slower, or finds no card at all. Usually a driver update went wrong, or one "
    'driver was installed over another.',
    'NVIDIA: download the current driver from nvidia.com, start it, choose Custom (Advanced) and tick Perform a '
    'clean installation.',
    'AMD: start the current AMD Software (Adrenalin) installer and choose Factory Reset.',
    'Still the same: remove the driver with Display Driver Uninstaller (DDU) in Safe Mode, then install it again.',
    'VK_ICD_FILENAMES or VK_DRIVER_FILES in the Windows environment variables: delete them. Vulkan then loads only '
    'the drivers they name.',
]

TEXTS = {
    'ru': [
        'Windows видит {0}, но её драйвер Vulkan не отвечает, поэтому игра работает на {1}, намного медленнее. '
        'Переустановите драйвер для {0} (чистая установка), затем перезагрузите ПК.',
        'Windows видит {0}, но её драйвер Vulkan не отвечает. Переустановите драйвер для {0} (чистая установка), '
        'затем перезагрузите ПК.',
        '{} не используется: её драйвер Vulkan не отвечает («Помощь»)',
        'Игра не использует вашу видеокарту',
        'Windows видит видеокарту, но её драйвер Vulkan не отвечает или слишком старый для порта: тогда игра работает на встроенной графике '
        'процессора, намного медленнее, или вообще не находит видеокарту. Обычно обновление драйвера прошло '
        'неудачно или один драйвер установили поверх другого.',
        'NVIDIA: скачайте актуальный драйвер с nvidia.com, запустите его, выберите «Выборочная установка '
        '(расширенные параметры)» и отметьте «Выполнить чистую установку».',
        'AMD: запустите установщик актуального AMD Software (Adrenalin) и выберите «Сброс к заводским настройкам» '
        '(Factory Reset).',
        'Если ничего не изменилось: удалите драйвер с помощью Display Driver Uninstaller (DDU) в безопасном режиме, '
        'затем установите его снова.',
        'VK_ICD_FILENAMES или VK_DRIVER_FILES в переменных среды Windows: удалите их. Иначе Vulkan загружает только '
        'те драйверы, которые в них указаны.',
    ],
    'ar': [
        'يتعرّف Windows على {0}، لكن تعريف Vulkan الخاص بها لا يستجيب، لذلك تعمل اللعبة على {1} بشكل أبطأ بكثير. '
        'أعد تثبيت تعريف {0} (تثبيت نظيف)، ثم أعد تشغيل الحاسوب.',
        'يتعرّف Windows على {0}، لكن تعريف Vulkan الخاص بها لا يستجيب. أعد تثبيت تعريف {0} (تثبيت نظيف)، ثم أعد '
        'تشغيل الحاسوب.',
        '{} غير مستخدمة: تعريف Vulkan الخاص بها لا يستجيب (المساعدة)',
        'اللعبة لا تستخدم بطاقة الرسومات لديك',
        'يتعرّف Windows على البطاقة، لكن تعريف Vulkan الخاص بها لا يستجيب أو أقدم من أن يناسب المنفذ: عندها تعمل اللعبة على رسوميات المعالج '
        'بشكل أبطأ بكثير، أو لا تجد أي بطاقة. غالبًا فشل تحديث للتعريف، أو ثُبّت تعريف فوق آخر.',
        'NVIDIA: نزّل أحدث تعريف من nvidia.com، وشغّله، واختر مخصص (متقدم)، وفعّل خيار إجراء تثبيت نظيف.',
        'AMD: شغّل مثبّت AMD Software (Adrenalin) الحالي واختر إعادة ضبط المصنع (Factory Reset).',
        'إذا بقي الأمر كما هو: أزل التعريف باستخدام Display Driver Uninstaller (DDU) في الوضع الآمن، ثم ثبّته من '
        'جديد.',
        'إذا وُجد VK_ICD_FILENAMES أو VK_DRIVER_FILES في متغيرات بيئة Windows فاحذفهما. وإلا فإن Vulkan يحمّل '
        'التعريفات التي يذكرانها فقط.',
    ],
    'es': [
        'Windows tiene {0}, pero su controlador Vulkan no responde, así que el juego funciona en {1}, mucho más '
        'lento. Reinstala el controlador de {0} (instalación limpia) y luego reinicia el PC.',
        'Windows tiene {0}, pero su controlador Vulkan no responde. Reinstala el controlador de {0} (instalación '
        'limpia) y luego reinicia el PC.',
        '{} no se usa: su controlador Vulkan no responde (Ayuda)',
        'El juego no usa tu tarjeta gráfica',
        'Windows tiene la tarjeta, pero su controlador Vulkan no responde o es demasiado antiguo para el port: el juego funciona entonces con los '
        'gráficos del procesador, mucho más lento, o no encuentra ninguna tarjeta. Normalmente una actualización '
        'del controlador salió mal o se instaló un controlador encima de otro.',
        'NVIDIA: descarga el controlador actual de nvidia.com, ejecútalo, elige Personalizada (avanzada) y marca '
        'Realizar una instalación limpia.',
        'AMD: ejecuta el instalador actual de AMD Software (Adrenalin) y elige Restablecimiento de fábrica (Factory '
        'Reset).',
        'Si sigue igual: elimina el controlador con Display Driver Uninstaller (DDU) en modo seguro y vuelve a '
        'instalarlo.',
        'VK_ICD_FILENAMES o VK_DRIVER_FILES en las variables de entorno de Windows: bórralas. Si no, Vulkan solo '
        'carga los controladores que nombran.',
    ],
    'pt': [
        'O Windows tem {0}, mas o driver Vulkan dela não responde, então o jogo roda em {1}, bem mais lento. '
        'Reinstale o driver de {0} (instalação limpa) e depois reinicie o PC.',
        'O Windows tem {0}, mas o driver Vulkan dela não responde. Reinstale o driver de {0} (instalação limpa) e '
        'depois reinicie o PC.',
        '{} não é usada: o driver Vulkan dela não responde (Ajuda)',
        'O jogo não usa sua placa de vídeo',
        'O Windows tem a placa, mas o driver Vulkan dela não responde ou é antigo demais para o port: o jogo então roda nos gráficos do '
        'processador, bem mais lento, ou não encontra nenhuma placa. Normalmente uma atualização de driver deu '
        'errado ou um driver foi instalado por cima de outro.',
        'NVIDIA: baixe o driver atual em nvidia.com, execute-o, escolha Personalizada (avançada) e marque Executar '
        'uma instalação limpa.',
        'AMD: execute o instalador atual do AMD Software (Adrenalin) e escolha Redefinição de fábrica (Factory '
        'Reset).',
        'Continua igual: remova o driver com o Display Driver Uninstaller (DDU) no Modo de Segurança e instale-o '
        'de novo.',
        'VK_ICD_FILENAMES ou VK_DRIVER_FILES nas variáveis de ambiente do Windows: apague-as. Senão o Vulkan '
        'carrega só os drivers que elas indicam.',
    ],
    'fr': [
        'Windows a {0}, mais son pilote Vulkan ne répond pas : le jeu tourne donc sur {1}, bien plus lentement. '
        'Réinstallez le pilote de {0} (installation propre), puis redémarrez le PC.',
        'Windows a {0}, mais son pilote Vulkan ne répond pas. Réinstallez le pilote de {0} (installation propre), '
        'puis redémarrez le PC.',
        '{} n’est pas utilisée : son pilote Vulkan ne répond pas (Aide)',
        'Le jeu n’utilise pas votre carte graphique',
        'Windows a la carte, mais son pilote Vulkan ne répond pas ou est trop ancien pour le port : le jeu tourne alors sur la partie graphique du '
        'processeur, bien plus lentement, ou ne trouve aucune carte. Le plus souvent, une mise à jour du pilote a '
        'échoué ou un pilote a été installé par-dessus un autre.',
        'NVIDIA : téléchargez le pilote actuel sur nvidia.com, lancez-le, choisissez Personnalisée (avancée) et '
        'cochez Effectuer une nouvelle installation.',
        'AMD : lancez le programme d’installation actuel d’AMD Software (Adrenalin) et choisissez Réinitialisation '
        'd’usine (Factory Reset).',
        'Toujours pareil : supprimez le pilote avec Display Driver Uninstaller (DDU) en mode sans échec, puis '
        'réinstallez-le.',
        'VK_ICD_FILENAMES ou VK_DRIVER_FILES dans les variables d’environnement de Windows : supprimez-les. Sinon '
        'Vulkan ne charge que les pilotes qu’elles nomment.',
    ],
    'de': [
        'Windows kennt {0}, doch der Vulkan-Treiber dafür antwortet nicht, darum läuft das Spiel auf {1}, viel '
        'langsamer. Installiere den Treiber für {0} neu (saubere Installation) und starte dann den PC neu.',
        'Windows kennt {0}, doch der Vulkan-Treiber dafür antwortet nicht. Installiere den Treiber für {0} neu '
        '(saubere Installation) und starte dann den PC neu.',
        '{} wird nicht genutzt: Der Vulkan-Treiber dafür antwortet nicht (Hilfe)',
        'Das Spiel nutzt deine Grafikkarte nicht',
        'Windows kennt die Karte, doch ihr Vulkan-Treiber antwortet nicht oder ist zu alt für den Port: Das Spiel läuft dann auf der Grafik des '
        'Prozessors, viel langsamer, oder findet gar keine Karte. Meist ist ein Treiber-Update schiefgegangen, oder '
        'ein Treiber wurde über einen anderen installiert.',
        'NVIDIA: Lade den aktuellen Treiber von nvidia.com, starte ihn, wähle Benutzerdefiniert (Erweitert) und '
        'hake „Neuinstallation durchführen“ an.',
        'AMD: Starte den Installer der aktuellen AMD Software (Adrenalin) und wähle „Auf Werkseinstellungen '
        'zurücksetzen“ (Factory Reset).',
        'Immer noch gleich: Entferne den Treiber mit Display Driver Uninstaller (DDU) im abgesicherten Modus und '
        'installiere ihn dann neu.',
        'VK_ICD_FILENAMES oder VK_DRIVER_FILES in den Windows-Umgebungsvariablen: Lösche sie. Vulkan lädt sonst nur '
        'die Treiber, die sie nennen.',
    ],
    'it': [
        'Windows ha {0}, ma il suo driver Vulkan non risponde, quindi il gioco gira su {1}, molto più lento. '
        'Reinstalla il driver di {0} (installazione pulita), poi riavvia il PC.',
        'Windows ha {0}, ma il suo driver Vulkan non risponde. Reinstalla il driver di {0} (installazione pulita), '
        'poi riavvia il PC.',
        '{} non viene usata: il suo driver Vulkan non risponde (Aiuto)',
        'Il gioco non usa la tua scheda video',
        'Windows ha la scheda, ma il suo driver Vulkan non risponde o è troppo vecchio per il port: il gioco gira allora sulla grafica del '
        'processore, molto più lento, o non trova nessuna scheda. Di solito un aggiornamento del driver è andato '
        'storto o un driver è stato installato sopra un altro.',
        'NVIDIA: scarica il driver attuale da nvidia.com, avvialo, scegli Personalizzata (avanzata) e spunta '
        "Esegui un'installazione pulita.",
        'AMD: avvia il programma di installazione attuale di AMD Software (Adrenalin) e scegli Ripristino delle '
        'impostazioni di fabbrica (Factory Reset).',
        'Ancora uguale: rimuovi il driver con Display Driver Uninstaller (DDU) in modalità provvisoria, poi '
        'installalo di nuovo.',
        "VK_ICD_FILENAMES o VK_DRIVER_FILES nelle variabili d'ambiente di Windows: eliminale. Altrimenti Vulkan "
        'carica solo i driver che indicano.',
    ],
    'pl': [
        'Windows wykrywa {0}, ale sterownik Vulkan tej karty nie odpowiada, więc gra działa na {1}, dużo wolniej. '
        'Zainstaluj ponownie sterownik dla {0} (czysta instalacja), a potem uruchom ponownie PC.',
        'Windows wykrywa {0}, ale sterownik Vulkan tej karty nie odpowiada. Zainstaluj ponownie sterownik dla {0} '
        '(czysta instalacja), a potem uruchom ponownie PC.',
        '{} nie jest używana: sterownik Vulkan tej karty nie odpowiada (Pomoc)',
        'Gra nie używa twojej karty graficznej',
        'Windows wykrywa kartę, ale jej sterownik Vulkan nie odpowiada lub jest za stary dla portu: gra działa wtedy na grafice procesora, dużo '
        'wolniej, albo nie znajduje żadnej karty. Zwykle aktualizacja sterownika się nie powiodła albo jeden '
        'sterownik zainstalowano na drugim.',
        'NVIDIA: pobierz aktualny sterownik z nvidia.com, uruchom go, wybierz Niestandardowa (zaawansowana) i '
        'zaznacz Wykonaj czystą instalację.',
        'AMD: uruchom aktualny instalator AMD Software (Adrenalin) i wybierz Przywracanie ustawień fabrycznych '
        '(Factory Reset).',
        'Nadal to samo: usuń sterownik programem Display Driver Uninstaller (DDU) w trybie awaryjnym, a potem '
        'zainstaluj go ponownie.',
        'VK_ICD_FILENAMES lub VK_DRIVER_FILES w zmiennych środowiskowych Windows: usuń je. Inaczej Vulkan wczytuje '
        'tylko sterowniki, które wskazują.',
    ],
    'tr': [
        'Windows {0} kartını görüyor, ancak kartın Vulkan sürücüsü yanıt vermiyor; bu yüzden oyun {1} üzerinde, '
        'çok daha yavaş çalışıyor. {0} sürücüsünü yeniden kurun (temiz kurulum), ardından bilgisayarı yeniden '
        'başlatın.',
        'Windows {0} kartını görüyor, ancak kartın Vulkan sürücüsü yanıt vermiyor. {0} sürücüsünü yeniden kurun '
        '(temiz kurulum), ardından bilgisayarı yeniden başlatın.',
        '{} kullanılmıyor: Vulkan sürücüsü yanıt vermiyor (Yardım)',
        'Oyun ekran kartınızı kullanmıyor',
        'Windows kartı görüyor, ancak kartın Vulkan sürücüsü yanıt vermiyor veya port için fazla eski: oyun o zaman işlemcinin grafik '
        'biriminde, çok daha yavaş çalışır ya da hiç kart bulamaz. Genellikle bir sürücü güncellemesi ters '
        'gitmiştir veya bir sürücü diğerinin üzerine kurulmuştur.',
        "NVIDIA: güncel sürücüyü nvidia.com'dan indirin, çalıştırın, Özel (Gelişmiş) seçeneğini seçin ve Temiz "
        'kurulum gerçekleştir kutusunu işaretleyin.',
        'AMD: güncel AMD Software (Adrenalin) yükleyicisini çalıştırın ve Fabrika Ayarlarına Sıfırla (Factory '
        'Reset) seçeneğini seçin.',
        "Hâlâ aynıysa: sürücüyü Güvenli Mod'da Display Driver Uninstaller (DDU) ile kaldırın, sonra yeniden kurun.",
        'Windows ortam değişkenlerinde VK_ICD_FILENAMES veya VK_DRIVER_FILES varsa silin. Aksi halde Vulkan '
        'yalnızca bunların belirttiği sürücüleri yükler.',
    ],
    'zh': [
        'Windows 识别到了 {0}，但它的 Vulkan 驱动没有响应，所以游戏在 {1} 上运行，慢得多。请重新安装 {0} 的驱动'
        '（清洁安装），然后重启电脑。',
        'Windows 识别到了 {0}，但它的 Vulkan 驱动没有响应。请重新安装 {0} 的驱动（清洁安装），然后重启电脑。',
        '{} 未被使用：它的 Vulkan 驱动没有响应（帮助）',
        '游戏没有使用你的显卡',
        'Windows 识别到了显卡，但它的 Vulkan 驱动没有响应或对本移植来说太旧：游戏会在处理器的核显上运行，慢得多，或者根本找不到显卡。'
        '通常是驱动更新出了问题，或者一个驱动被装在了另一个之上。',
        'NVIDIA：从 nvidia.com 下载最新驱动，运行后选择“自定义（高级）”，并勾选“执行清洁安装”。',
        'AMD：运行最新的 AMD Software (Adrenalin) 安装程序，选择“恢复出厂设置”（Factory Reset）。',
        '仍然一样：在安全模式下用 Display Driver Uninstaller (DDU) 卸载驱动，然后重新安装。',
        'Windows 环境变量中有 VK_ICD_FILENAMES 或 VK_DRIVER_FILES：请删除它们。否则 Vulkan 只加载它们指定的驱动。',
    ],
    'ja': [
        'Windows は {0} を認識していますが、その Vulkan ドライバーが応答しないため、ゲームは {1} でずっと遅く動作して'
        'います。{0} のドライバーを入れ直し（クリーンインストール）、PC を再起動してください。',
        'Windows は {0} を認識していますが、その Vulkan ドライバーが応答しません。{0} のドライバーを入れ直し'
        '（クリーンインストール）、PC を再起動してください。',
        '{} が使われていません：Vulkan ドライバーが応答しません（ヘルプ）',
        'ゲームがグラフィックカードを使っていない',
        'Windows はカードを認識していますが、その Vulkan ドライバーが応答しないか移植版には古すぎます：ゲームはプロセッサー内蔵のグラフィック'
        'でずっと遅く動作するか、カードをまったく見つけられません。多くの場合、ドライバーの更新に失敗したか、別の'
        'ドライバーの上に重ねてインストールされています。',
        'NVIDIA：nvidia.com から最新のドライバーをダウンロードして起動し、「カスタム (詳細)」を選んで「クリーン'
        'インストールの実行」にチェックを入れてください。',
        'AMD：最新の AMD Software (Adrenalin) インストーラーを起動し、「工場出荷時の状態にリセット」(Factory Reset) '
        'を選んでください。',
        'それでも変わらない場合：セーフモードで Display Driver Uninstaller (DDU) を使ってドライバーを削除し、もう一度'
        'インストールしてください。',
        'Windows の環境変数に VK_ICD_FILENAMES または VK_DRIVER_FILES がある場合は削除してください。あると Vulkan は'
        'そこに書かれたドライバーしか読み込みません。',
    ],
    'ko': [
        'Windows는 {0}을(를) 인식하지만 그 Vulkan 드라이버가 응답하지 않아 게임이 {1}에서 훨씬 느리게 실행됩니다. '
        '{0} 드라이버를 다시 설치(클린 설치)한 뒤 PC를 다시 시작하세요.',
        'Windows는 {0}을(를) 인식하지만 그 Vulkan 드라이버가 응답하지 않습니다. {0} 드라이버를 다시 설치(클린 설치)한 '
        '뒤 PC를 다시 시작하세요.',
        '{}이(가) 사용되지 않음: Vulkan 드라이버가 응답하지 않음 (도움말)',
        '게임이 그래픽 카드를 사용하지 않음',
        'Windows는 카드를 인식하지만 그 Vulkan 드라이버가 응답하지 않거나 포트에 비해 너무 오래되었습니다: 그러면 게임이 프로세서 내장 그래픽에서 '
        '훨씬 느리게 실행되거나 카드를 전혀 찾지 못합니다. 보통 드라이버 업데이트가 잘못되었거나 한 드라이버를 다른 '
        '드라이버 위에 설치한 경우입니다.',
        'NVIDIA: nvidia.com에서 최신 드라이버를 내려받아 실행하고, 사용자 정의 설치(고급)를 고른 뒤 클린 설치 수행에 '
        '체크하세요.',
        'AMD: 최신 AMD Software (Adrenalin) 설치 프로그램을 실행하고 공장 초기화(Factory Reset)를 선택하세요.',
        '그래도 같다면: 안전 모드에서 Display Driver Uninstaller(DDU)로 드라이버를 제거한 뒤 다시 설치하세요.',
        'Windows 환경 변수에 VK_ICD_FILENAMES 또는 VK_DRIVER_FILES가 있으면 삭제하세요. 그렇지 않으면 Vulkan은 거기에 '
        '적힌 드라이버만 불러옵니다.',
    ],
}

for _language, _texts in TEXTS.items():
    assert len(_texts) == len(KEYS), (_language, len(_texts), len(KEYS))
    bbport_lang.EXTRA_TRANSLATIONS.setdefault(_language, {}).update(zip(KEYS, _texts))
