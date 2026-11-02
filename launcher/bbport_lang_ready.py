# SPDX-License-Identifier: GPL-2.0-or-later
"""The texts of the start's other prerequisites (the Play page's ready check, Help's check and topics): the Visual
C++ runtime AMD's DirectX 12 files need, a game folder in OneDrive, the game files against the clean 1.09, the
firewall, a graphics card its driver holds back, the clean eboot.bin put back. In every language besides English;
keyed by the English text like bbport_lang, merged into its tables on import."""
import bbport_lang

KEYS = [
    # Help's topics, their buttons
    'The Microsoft Visual C++ Redistributable is missing',
    "AMD's FSR 4 and frame generation files for DirectX 12 need it. Without it Windows cannot load them, and the "
    'launcher offers them as unavailable.',
    'Download it from Microsoft (the button below), run it and let it install.',
    'Then close the launcher and start it again.',
    'The game folder is in a synced folder',
    'OneDrive, Dropbox and Google Drive keep files online only until they are opened, and lock them while they '
    'sync: the game then hangs while loading or shows only a black screen.',
    'Move the whole game folder (the one with eboot.bin) to a plain folder like C:\\Games\\CUSA03173.',
    'Then choose it again (the button below).',
    'Game files are damaged',
    'Files of the game folder are not those of the clean 1.09: a copy or an unpack that went wrong, or a mod copied '
    'into the game folder. The game can then hang while loading, lose parts of the map, or crash in one place.',
    'Unpack the base game and the 1.09 update into a new, empty folder again, and copy the update over the base '
    'game.',
    'Or copy only the files the check names from that new unpack into your game folder.',
    'Mods belong on the Mods page, not in the game folder.',
    'Windows Firewall blocks the game',
    "Windows asked whether bb-probe.exe may use the network, and the answer was Cancel: it now blocks the game's "
    'incoming connections, and summons or joining others can fail.',
    'Click the button below: Windows Defender Firewall with Advanced Security opens.',
    'Inbound Rules: delete the rules named bb-probe.exe that have a red sign (right-click > Delete).',
    'Start the game online, and when Windows asks again, click Allow.',
    'Download it from Microsoft',
    'Check the game files',
    'Open the firewall settings',
    # Help's check
    'eboot.bin was not the clean 1.09 file: the clean copy from {0} is used now, the other one is kept as {1}.',
    '{0} files of the game are kept online only by OneDrive or another cloud program, for example {1}: the game '
    'hangs when it loads them.',
    'The game folder is in a synced folder: {}.',
    "Windows Firewall blocks the game's incoming connections: co-op can fail.",
    "AMD's FSR 4 files could not be loaded: the Microsoft Visual C++ Redistributable is missing ({}).",
    '{0} is not used: its driver lacks {1}, so the game runs on {2}, much slower. Install the current driver for '
    '{0} (clean installation), then restart the PC.',
    # the game files' check
    'No game folder chosen yet.',
    'Checking the game files… {}%',
    'All {} game files are those of the clean 1.09.',
    '{0} of {1} game files differ from the clean 1.09 or are missing, for example: {2}. See "Game files are '
    'damaged" below.',
    'Compares every file with the clean 1.09 (a few minutes).',
    # the Play page's ready check
    '{} is not used: its driver is too old for the port (Help)',
    'The game folder is in OneDrive or another synced folder: move it (Help)',
    'AMD FSR 4 needs the Microsoft Visual C++ Redistributable: click to download it',
    'Windows Firewall blocks the game: co-op can fail (Help)',
]

TEXTS = {
    'ru': [
        'Не установлен Microsoft Visual C++ Redistributable',
        'Он нужен файлам AMD FSR 4 и генерации кадров для DirectX 12. Без него Windows не может их загрузить, и '
        'лаунчер показывает их как недоступные.',
        'Скачайте его с сайта Microsoft (кнопка ниже), запустите и дайте ему установиться.',
        'Затем закройте лаунчер и запустите его снова.',
        'Папка игры находится в синхронизируемой папке',
        'OneDrive, Dropbox и Google Drive хранят файлы только в облаке, пока их не откроют, и блокируют их во '
        'время синхронизации: тогда игра зависает при загрузке или показывает только чёрный экран.',
        'Переместите всю папку игры (ту, где лежит eboot.bin) в обычную папку, например C:\\Games\\CUSA03173.',
        'Затем выберите её снова (кнопка ниже).',
        'Файлы игры повреждены',
        'Файлы в папке игры не совпадают с чистой версией 1.09: копирование или распаковка прошли с ошибкой, или '
        'мод был скопирован в папку игры. Тогда игра может зависать при загрузке, терять части карты или вылетать в '
        'одном месте.',
        'Заново распакуйте базовую игру и обновление 1.09 в новую пустую папку и скопируйте обновление поверх '
        'базовой игры.',
        'Или скопируйте из этой новой распаковки в свою папку игры только файлы, которые назвала проверка.',
        'Моды добавляются на странице «Моды», а не в папку игры.',
        'Брандмауэр Windows блокирует игру',
        'Windows спросила, может ли bb-probe.exe использовать сеть, и был выбран ответ «Отмена»: теперь она '
        'блокирует входящие подключения игры, и призыв или присоединение к другим может не работать.',
        'Нажмите кнопку ниже: откроется «Монитор брандмауэра Защитника Windows в режиме повышенной безопасности».',
        'Правила для входящих подключений: удалите правила с именем bb-probe.exe и красным значком (правый щелчок > '
        'Удалить).',
        'Запустите игру онлайн и, когда Windows спросит снова, нажмите «Разрешить».',
        'Скачать с сайта Microsoft',
        'Проверить файлы игры',
        'Открыть настройки брандмауэра',
        'eboot.bin был не чистым файлом 1.09: теперь используется чистая копия из {0}, прежний сохранён как {1}.',
        '{0} файлов игры хранятся только в облаке OneDrive или другой облачной программы, например {1}: игра '
        'зависает, когда загружает их.',
        'Папка игры находится в синхронизируемой папке: {}.',
        'Брандмауэр Windows блокирует входящие подключения игры: совместная игра может не работать.',
        'Файлы AMD FSR 4 не удалось загрузить: не установлен Microsoft Visual C++ Redistributable ({}).',
        '{0} не используется: её драйверу не хватает {1}, поэтому игра работает на {2}, намного медленнее. '
        'Установите актуальный драйвер для {0} (чистая установка), затем перезагрузите ПК.',
        'Папка игры ещё не выбрана.',
        'Проверка файлов игры… {}%',
        'Все {} файлов игры совпадают с чистой версией 1.09.',
        '{0} из {1} файлов игры отличаются от чистой версии 1.09 или отсутствуют, например: {2}. См. «Файлы игры '
        'повреждены» ниже.',
        'Сравнивает каждый файл с чистой версией 1.09 (несколько минут).',
        '{} не используется: её драйвер слишком старый для порта («Помощь»)',
        'Папка игры находится в OneDrive или другой синхронизируемой папке: переместите её («Помощь»)',
        'Для AMD FSR 4 нужен Microsoft Visual C++ Redistributable: нажмите, чтобы скачать',
        'Брандмауэр Windows блокирует игру: совместная игра может не работать («Помощь»)',
    ],
    'ar': [
        'حزمة Microsoft Visual C++ Redistributable غير مثبتة',
        'تحتاجها ملفات AMD FSR 4 وتوليد الإطارات لـ DirectX 12. بدونها لا يستطيع Windows تحميلها، ويعرضها '
        'المشغّل على أنها غير متاحة.',
        'نزّلها من Microsoft (الزر أدناه)، وشغّلها ودعها تكتمل.',
        'ثم أغلق المشغّل وشغّله من جديد.',
        'مجلد اللعبة داخل مجلد متزامن',
        'تحتفظ OneDrive وDropbox وGoogle Drive بالملفات على الإنترنت فقط حتى تُفتح، وتقفلها أثناء المزامنة: '
        'عندها تتجمد اللعبة أثناء التحميل أو تعرض شاشة سوداء فقط.',
        'انقل مجلد اللعبة كاملًا (الذي فيه eboot.bin) إلى مجلد عادي مثل C:\\Games\\CUSA03173.',
        'ثم اختره من جديد (الزر أدناه).',
        'ملفات اللعبة تالفة',
        'ملفات مجلد اللعبة ليست ملفات الإصدار 1.09 السليم: نسخ أو فك ضغط فشل، أو تعديل نُسخ إلى مجلد اللعبة. '
        'عندها قد تتجمد اللعبة أثناء التحميل، أو تفقد أجزاء من الخريطة، أو تنهار في مكان واحد.',
        'فك ضغط اللعبة الأساسية وتحديث 1.09 من جديد في مجلد جديد فارغ، وانسخ التحديث فوق اللعبة الأساسية.',
        'أو انسخ فقط الملفات التي يذكرها الفحص من ذلك الفك الجديد إلى مجلد لعبتك.',
        'مكان التعديلات صفحة Mods، وليس مجلد اللعبة.',
        'جدار حماية Windows يحظر اللعبة',
        'سأل Windows هل يُسمح لـ bb-probe.exe باستخدام الشبكة، وكان الجواب إلغاء: صار يحظر الاتصالات الواردة '
        'للعبة، وقد يفشل الاستدعاء أو الانضمام إلى الآخرين.',
        'انقر الزر أدناه: يُفتح جدار حماية Windows Defender مع الأمان المتقدم.',
        'القواعد الواردة: احذف القواعد باسم bb-probe.exe التي عليها علامة حمراء (انقر بالزر الأيمن > حذف).',
        'شغّل اللعبة عبر الإنترنت، وعندما يسأل Windows مرة أخرى انقر سماح.',
        'التنزيل من Microsoft',
        'فحص ملفات اللعبة',
        'فتح إعدادات جدار الحماية',
        'لم يكن eboot.bin ملف 1.09 السليم: تُستخدم الآن النسخة السليمة من {0}، والآخر محفوظ باسم {1}.',
        '{0} من ملفات اللعبة محفوظة على الإنترنت فقط بواسطة OneDrive أو برنامج سحابي آخر، مثل {1}: تتجمد اللعبة '
        'عندما تحمّلها.',
        'مجلد اللعبة داخل مجلد متزامن: {}.',
        'جدار حماية Windows يحظر الاتصالات الواردة للعبة: قد يفشل اللعب الجماعي.',
        'تعذّر تحميل ملفات AMD FSR 4: حزمة Microsoft Visual C++ Redistributable غير مثبتة ({}).',
        '{0} غير مستخدمة: ينقص تعريفها {1}، لذلك تعمل اللعبة على {2} بشكل أبطأ بكثير. ثبّت أحدث تعريف لـ {0} '
        '(تثبيت نظيف)، ثم أعد تشغيل الحاسوب.',
        'لم يُختر مجلد اللعبة بعد.',
        'جارٍ فحص ملفات اللعبة… {}%',
        'كل ملفات اللعبة البالغ عددها {} مطابقة لإصدار 1.09 السليم.',
        '{0} من {1} ملفًا من ملفات اللعبة تختلف عن 1.09 السليم أو مفقودة، مثل: {2}. انظر "ملفات اللعبة تالفة" '
        'أدناه.',
        'يقارن كل ملف بإصدار 1.09 السليم (بضع دقائق).',
        '{} غير مستخدمة: تعريفها قديم جدًا للمنفذ (المساعدة)',
        'مجلد اللعبة داخل OneDrive أو مجلد متزامن آخر: انقله (المساعدة)',
        'يحتاج AMD FSR 4 إلى Microsoft Visual C++ Redistributable: انقر لتنزيلها',
        'جدار حماية Windows يحظر اللعبة: قد يفشل اللعب الجماعي (المساعدة)',
    ],
    'es': [
        'Falta Microsoft Visual C++ Redistributable',
        'Lo necesitan los archivos de AMD FSR 4 y de generación de fotogramas para DirectX 12. Sin él, Windows no '
        'puede cargarlos y el launcher los muestra como no disponibles.',
        'Descárgalo de Microsoft (el botón de abajo), ejecútalo y deja que se instale.',
        'Después cierra el launcher y vuelve a abrirlo.',
        'La carpeta del juego está en una carpeta sincronizada',
        'OneDrive, Dropbox y Google Drive guardan los archivos solo en línea hasta que se abren, y los bloquean '
        'mientras sincronizan: el juego se queda colgado al cargar o muestra solo una pantalla negra.',
        'Mueve toda la carpeta del juego (la que tiene eboot.bin) a una carpeta normal como C:\\Games\\CUSA03173.',
        'Después vuelve a elegirla (el botón de abajo).',
        'Los archivos del juego están dañados',
        'Hay archivos de la carpeta del juego que no son los de la 1.09 limpia: una copia o una descompresión que '
        'salió mal, o un mod copiado en la carpeta del juego. El juego puede colgarse al cargar, perder partes del '
        'mapa o cerrarse siempre en el mismo sitio.',
        'Descomprime de nuevo el juego base y la actualización 1.09 en una carpeta nueva y vacía, y copia la '
        'actualización encima del juego base.',
        'O copia de esa nueva descompresión a tu carpeta del juego solo los archivos que nombra la comprobación.',
        'Los mods van en la página Mods, no en la carpeta del juego.',
        'El Firewall de Windows bloquea el juego',
        'Windows preguntó si bb-probe.exe podía usar la red y la respuesta fue Cancelar: ahora bloquea las '
        'conexiones entrantes del juego, y las invocaciones o unirse a otros pueden fallar.',
        'Pulsa el botón de abajo: se abre Firewall de Windows Defender con seguridad avanzada.',
        'Reglas de entrada: elimina las reglas llamadas bb-probe.exe que tienen un símbolo rojo (clic derecho > '
        'Eliminar).',
        'Inicia el juego en línea y, cuando Windows vuelva a preguntar, pulsa Permitir.',
        'Descargarlo de Microsoft',
        'Comprobar los archivos del juego',
        'Abrir la configuración del firewall',
        'eboot.bin no era el archivo limpio de la 1.09: ahora se usa la copia limpia de {0}, el otro se guarda como '
        '{1}.',
        '{0} archivos del juego están solo en línea en OneDrive u otro programa en la nube, por ejemplo {1}: el '
        'juego se cuelga cuando los carga.',
        'La carpeta del juego está en una carpeta sincronizada: {}.',
        'El Firewall de Windows bloquea las conexiones entrantes del juego: el cooperativo puede fallar.',
        'No se pudieron cargar los archivos de AMD FSR 4: falta Microsoft Visual C++ Redistributable ({}).',
        '{0} no se usa: a su controlador le falta {1}, así que el juego funciona en {2}, mucho más lento. Instala '
        'el controlador actual de {0} (instalación limpia) y luego reinicia el PC.',
        'Todavía no se ha elegido la carpeta del juego.',
        'Comprobando los archivos del juego… {}%',
        'Los {} archivos del juego son los de la 1.09 limpia.',
        '{0} de {1} archivos del juego difieren de la 1.09 limpia o faltan, por ejemplo: {2}. Mira «Los archivos '
        'del juego están dañados» más abajo.',
        'Compara cada archivo con la 1.09 limpia (unos minutos).',
        '{} no se usa: su controlador es demasiado antiguo para el port (Ayuda)',
        'La carpeta del juego está en OneDrive u otra carpeta sincronizada: muévela (Ayuda)',
        'AMD FSR 4 necesita Microsoft Visual C++ Redistributable: haz clic para descargarlo',
        'El Firewall de Windows bloquea el juego: el cooperativo puede fallar (Ayuda)',
    ],
    'pt': [
        'O Microsoft Visual C++ Redistributable está faltando',
        'Os arquivos do AMD FSR 4 e da geração de quadros para DirectX 12 precisam dele. Sem ele o Windows não '
        'consegue carregá-los, e o launcher os mostra como indisponíveis.',
        'Baixe-o da Microsoft (o botão abaixo), execute-o e deixe instalar.',
        'Depois feche o launcher e abra-o de novo.',
        'A pasta do jogo está em uma pasta sincronizada',
        'OneDrive, Dropbox e Google Drive mantêm os arquivos só online até serem abertos, e os bloqueiam durante a '
        'sincronização: o jogo então trava ao carregar ou mostra só uma tela preta.',
        'Mova a pasta inteira do jogo (a que tem o eboot.bin) para uma pasta comum como C:\\Games\\CUSA03173.',
        'Depois escolha-a de novo (o botão abaixo).',
        'Os arquivos do jogo estão danificados',
        'Há arquivos da pasta do jogo que não são os da 1.09 limpa: uma cópia ou extração que deu errado, ou um mod '
        'copiado para a pasta do jogo. O jogo pode travar ao carregar, perder partes do mapa ou fechar sempre no '
        'mesmo lugar.',
        'Extraia de novo o jogo base e a atualização 1.09 em uma pasta nova e vazia, e copie a atualização por cima '
        'do jogo base.',
        'Ou copie dessa nova extração para a sua pasta do jogo só os arquivos que a verificação indica.',
        'Mods ficam na página Mods, não na pasta do jogo.',
        'O Firewall do Windows bloqueia o jogo',
        'O Windows perguntou se o bb-probe.exe podia usar a rede, e a resposta foi Cancelar: agora ele bloqueia as '
        'conexões de entrada do jogo, e invocações ou entrar no mundo de outros podem falhar.',
        'Clique no botão abaixo: abre o Firewall do Windows Defender com Segurança Avançada.',
        'Regras de Entrada: exclua as regras chamadas bb-probe.exe que têm um sinal vermelho (clique direito > '
        'Excluir).',
        'Inicie o jogo online e, quando o Windows perguntar de novo, clique em Permitir.',
        'Baixar da Microsoft',
        'Verificar os arquivos do jogo',
        'Abrir as configurações do firewall',
        'O eboot.bin não era o arquivo limpo da 1.09: agora é usada a cópia limpa de {0}, o outro foi guardado como '
        '{1}.',
        '{0} arquivos do jogo ficam só online no OneDrive ou em outro programa de nuvem, por exemplo {1}: o jogo '
        'trava quando os carrega.',
        'A pasta do jogo está em uma pasta sincronizada: {}.',
        'O Firewall do Windows bloqueia as conexões de entrada do jogo: o cooperativo pode falhar.',
        'Não foi possível carregar os arquivos do AMD FSR 4: o Microsoft Visual C++ Redistributable está faltando '
        '({}).',
        '{0} não é usada: falta {1} ao driver dela, então o jogo roda em {2}, bem mais lento. Instale o driver '
        'atual de {0} (instalação limpa) e depois reinicie o PC.',
        'Nenhuma pasta do jogo escolhida ainda.',
        'Verificando os arquivos do jogo… {}%',
        'Todos os {} arquivos do jogo são os da 1.09 limpa.',
        '{0} de {1} arquivos do jogo diferem da 1.09 limpa ou estão faltando, por exemplo: {2}. Veja "Os arquivos '
        'do jogo estão danificados" abaixo.',
        'Compara cada arquivo com a 1.09 limpa (alguns minutos).',
        '{} não é usada: o driver dela é antigo demais para o port (Ajuda)',
        'A pasta do jogo está no OneDrive ou em outra pasta sincronizada: mova-a (Ajuda)',
        'O AMD FSR 4 precisa do Microsoft Visual C++ Redistributable: clique para baixar',
        'O Firewall do Windows bloqueia o jogo: o cooperativo pode falhar (Ajuda)',
    ],
    'fr': [
        'Le Microsoft Visual C++ Redistributable est absent',
        'Les fichiers d’AMD FSR 4 et de la génération d’images pour DirectX 12 en ont besoin. Sans lui, Windows ne '
        'peut pas les charger, et le launcher les indique comme indisponibles.',
        'Téléchargez-le chez Microsoft (le bouton ci-dessous), lancez-le et laissez-le s’installer.',
        'Fermez ensuite le launcher et relancez-le.',
        'Le dossier du jeu est dans un dossier synchronisé',
        'OneDrive, Dropbox et Google Drive gardent les fichiers uniquement en ligne tant qu’ils ne sont pas ouverts, '
        'et les verrouillent pendant la synchronisation : le jeu se bloque alors au chargement ou n’affiche qu’un '
        'écran noir.',
        'Déplacez tout le dossier du jeu (celui qui contient eboot.bin) vers un dossier ordinaire comme '
        'C:\\Games\\CUSA03173.',
        'Puis choisissez-le à nouveau (le bouton ci-dessous).',
        'Des fichiers du jeu sont endommagés',
        'Des fichiers du dossier du jeu ne sont pas ceux de la 1.09 d’origine : une copie ou une extraction qui a '
        'échoué, ou un mod copié dans le dossier du jeu. Le jeu peut alors se bloquer au chargement, perdre des '
        'morceaux de la carte ou planter toujours au même endroit.',
        'Extrayez de nouveau le jeu de base et la mise à jour 1.09 dans un dossier neuf et vide, puis copiez la mise '
        'à jour par-dessus le jeu de base.',
        'Ou copiez seulement les fichiers que la vérification nomme depuis cette nouvelle extraction vers votre '
        'dossier du jeu.',
        'Les mods se mettent sur la page Mods, pas dans le dossier du jeu.',
        'Le pare-feu Windows bloque le jeu',
        'Windows a demandé si bb-probe.exe pouvait utiliser le réseau, et la réponse a été Annuler : il bloque '
        'désormais les connexions entrantes du jeu, et les invocations ou rejoindre d’autres joueurs peuvent échouer.',
        'Cliquez sur le bouton ci-dessous : le Pare-feu Windows Defender avec fonctions avancées de sécurité '
        's’ouvre.',
        'Règles de trafic entrant : supprimez les règles nommées bb-probe.exe qui ont un symbole rouge (clic droit > '
        'Supprimer).',
        'Lancez le jeu en ligne et, quand Windows redemande, cliquez sur Autoriser.',
        'Le télécharger chez Microsoft',
        'Vérifier les fichiers du jeu',
        'Ouvrir les paramètres du pare-feu',
        'eboot.bin n’était pas le fichier d’origine de la 1.09 : la copie propre de {0} est utilisée maintenant, '
        'l’autre est gardé sous le nom {1}.',
        '{0} fichiers du jeu sont gardés uniquement en ligne par OneDrive ou un autre programme cloud, par exemple '
        '{1} : le jeu se bloque quand il les charge.',
        'Le dossier du jeu est dans un dossier synchronisé : {}.',
        'Le pare-feu Windows bloque les connexions entrantes du jeu : la coopération peut échouer.',
        'Les fichiers d’AMD FSR 4 n’ont pas pu être chargés : le Microsoft Visual C++ Redistributable est absent '
        '({}).',
        '{0} n’est pas utilisée : il manque {1} à son pilote, le jeu tourne donc sur {2}, bien plus lentement. '
        'Installez le pilote actuel de {0} (installation propre), puis redémarrez le PC.',
        'Aucun dossier du jeu choisi pour l’instant.',
        'Vérification des fichiers du jeu… {} %',
        'Les {} fichiers du jeu sont ceux de la 1.09 d’origine.',
        '{0} des {1} fichiers du jeu diffèrent de la 1.09 d’origine ou manquent, par exemple : {2}. Voir « Des '
        'fichiers du jeu sont endommagés » plus bas.',
        'Compare chaque fichier avec la 1.09 d’origine (quelques minutes).',
        '{} n’est pas utilisée : son pilote est trop ancien pour le port (Aide)',
        'Le dossier du jeu est dans OneDrive ou un autre dossier synchronisé : déplacez-le (Aide)',
        'AMD FSR 4 a besoin du Microsoft Visual C++ Redistributable : cliquez pour le télécharger',
        'Le pare-feu Windows bloque le jeu : la coopération peut échouer (Aide)',
    ],
    'de': [
        'Microsoft Visual C++ Redistributable fehlt',
        'Die Dateien von AMD FSR 4 und der Bildgenerierung für DirectX 12 brauchen es. Ohne es kann Windows sie '
        'nicht laden, und der Launcher zeigt sie als nicht verfügbar.',
        'Lade es bei Microsoft herunter (Button unten), starte es und lass es installieren.',
        'Schließe dann den Launcher und starte ihn neu.',
        'Der Spielordner liegt in einem synchronisierten Ordner',
        'OneDrive, Dropbox und Google Drive halten Dateien nur online, bis sie geöffnet werden, und sperren sie '
        'beim Synchronisieren: Das Spiel hängt dann beim Laden oder zeigt nur einen schwarzen Bildschirm.',
        'Verschiebe den ganzen Spielordner (den mit eboot.bin) in einen normalen Ordner wie C:\\Games\\CUSA03173.',
        'Wähle ihn dann erneut aus (Button unten).',
        'Spieldateien sind beschädigt',
        'Dateien im Spielordner sind nicht die der sauberen 1.09: ein Kopieren oder Entpacken ist schiefgegangen, '
        'oder ein Mod wurde in den Spielordner kopiert. Das Spiel kann dann beim Laden hängen, Teile der Karte '
        'verlieren oder an einer Stelle abstürzen.',
        'Entpacke das Basisspiel und das Update 1.09 erneut in einen neuen, leeren Ordner und kopiere das Update '
        'über das Basisspiel.',
        'Oder kopiere nur die Dateien, die die Prüfung nennt, aus diesem neuen Entpacken in deinen Spielordner.',
        'Mods gehören auf die Seite Mods, nicht in den Spielordner.',
        'Die Windows-Firewall blockiert das Spiel',
        'Windows hat gefragt, ob bb-probe.exe das Netzwerk nutzen darf, und die Antwort war Abbrechen: Jetzt '
        'blockiert sie eingehende Verbindungen des Spiels, und Beschwörungen oder das Beitreten bei anderen können '
        'scheitern.',
        'Klicke auf den Button unten: Windows Defender Firewall mit erweiterter Sicherheit öffnet sich.',
        'Eingehende Regeln: Lösche die Regeln namens bb-probe.exe mit rotem Zeichen (Rechtsklick > Löschen).',
        'Starte das Spiel online und klicke auf Zulassen, wenn Windows erneut fragt.',
        'Bei Microsoft herunterladen',
        'Spieldateien prüfen',
        'Firewall-Einstellungen öffnen',
        'eboot.bin war nicht die saubere 1.09: Jetzt wird die saubere Kopie aus {0} genutzt, die andere bleibt als '
        '{1} erhalten.',
        '{0} Dateien des Spiels hält OneDrive oder ein anderes Cloud-Programm nur online, zum Beispiel {1}: Das '
        'Spiel hängt, wenn es sie lädt.',
        'Der Spielordner liegt in einem synchronisierten Ordner: {}.',
        'Die Windows-Firewall blockiert eingehende Verbindungen des Spiels: Koop kann scheitern.',
        'Die Dateien von AMD FSR 4 ließen sich nicht laden: Microsoft Visual C++ Redistributable fehlt ({}).',
        '{0} wird nicht genutzt: Dem Treiber fehlt {1}, darum läuft das Spiel auf {2}, viel langsamer. Installiere '
        'den aktuellen Treiber für {0} (saubere Installation) und starte dann den PC neu.',
        'Noch kein Spielordner gewählt.',
        'Spieldateien werden geprüft… {} %',
        'Alle {} Spieldateien sind die der sauberen 1.09.',
        '{0} von {1} Spieldateien weichen von der sauberen 1.09 ab oder fehlen, zum Beispiel: {2}. Siehe '
        '„Spieldateien sind beschädigt“ unten.',
        'Vergleicht jede Datei mit der sauberen 1.09 (ein paar Minuten).',
        '{} wird nicht genutzt: Der Treiber ist zu alt für den Port (Hilfe)',
        'Der Spielordner liegt in OneDrive oder einem anderen synchronisierten Ordner: verschiebe ihn (Hilfe)',
        'AMD FSR 4 braucht Microsoft Visual C++ Redistributable: Klicke zum Herunterladen',
        'Die Windows-Firewall blockiert das Spiel: Koop kann scheitern (Hilfe)',
    ],
    'it': [
        'Manca Microsoft Visual C++ Redistributable',
        'Serve ai file di AMD FSR 4 e della generazione dei fotogrammi per DirectX 12. Senza, Windows non riesce a '
        'caricarli e il launcher li mostra come non disponibili.',
        'Scaricalo da Microsoft (il pulsante qui sotto), avvialo e lascialo installare.',
        'Poi chiudi il launcher e riaprilo.',
        'La cartella del gioco è in una cartella sincronizzata',
        'OneDrive, Dropbox e Google Drive tengono i file solo online finché non vengono aperti, e li bloccano mentre '
        'sincronizzano: il gioco allora si blocca durante il caricamento o mostra solo una schermata nera.',
        'Sposta l\'intera cartella del gioco (quella con eboot.bin) in una cartella normale come '
        'C:\\Games\\CUSA03173.',
        'Poi sceglila di nuovo (il pulsante qui sotto).',
        'I file del gioco sono danneggiati',
        'Alcuni file della cartella del gioco non sono quelli della 1.09 pulita: una copia o un\'estrazione andata '
        'male, o una mod copiata nella cartella del gioco. Il gioco può bloccarsi durante il caricamento, perdere '
        'parti della mappa o chiudersi sempre nello stesso punto.',
        'Estrai di nuovo il gioco base e l\'aggiornamento 1.09 in una cartella nuova e vuota, e copia '
        'l\'aggiornamento sopra il gioco base.',
        'Oppure copia da quella nuova estrazione nella tua cartella del gioco solo i file che il controllo indica.',
        'Le mod vanno nella pagina Mods, non nella cartella del gioco.',
        'Windows Firewall blocca il gioco',
        'Windows ha chiesto se bb-probe.exe poteva usare la rete e la risposta è stata Annulla: ora blocca le '
        'connessioni in entrata del gioco, e le evocazioni o l\'ingresso nel mondo di altri possono fallire.',
        'Fai clic sul pulsante qui sotto: si apre Windows Defender Firewall con sicurezza avanzata.',
        'Regole connessioni in entrata: elimina le regole chiamate bb-probe.exe con un simbolo rosso (clic destro > '
        'Elimina).',
        'Avvia il gioco online e, quando Windows lo chiede di nuovo, fai clic su Consenti.',
        'Scaricalo da Microsoft',
        'Controlla i file del gioco',
        'Apri le impostazioni del firewall',
        'eboot.bin non era il file pulito della 1.09: ora si usa la copia pulita da {0}, l\'altro è conservato come '
        '{1}.',
        '{0} file del gioco sono tenuti solo online da OneDrive o da un altro programma cloud, per esempio {1}: il '
        'gioco si blocca quando li carica.',
        'La cartella del gioco è in una cartella sincronizzata: {}.',
        'Windows Firewall blocca le connessioni in entrata del gioco: la cooperativa può fallire.',
        'Impossibile caricare i file di AMD FSR 4: manca Microsoft Visual C++ Redistributable ({}).',
        '{0} non viene usata: al suo driver manca {1}, quindi il gioco gira su {2}, molto più lento. Installa il '
        'driver attuale di {0} (installazione pulita), poi riavvia il PC.',
        'Nessuna cartella del gioco scelta finora.',
        'Controllo dei file del gioco… {}%',
        'Tutti i {} file del gioco sono quelli della 1.09 pulita.',
        '{0} file del gioco su {1} differiscono dalla 1.09 pulita o mancano, per esempio: {2}. Vedi «I file del '
        'gioco sono danneggiati» qui sotto.',
        'Confronta ogni file con la 1.09 pulita (qualche minuto).',
        '{} non viene usata: il suo driver è troppo vecchio per il port (Aiuto)',
        'La cartella del gioco è in OneDrive o in un\'altra cartella sincronizzata: spostala (Aiuto)',
        'AMD FSR 4 richiede Microsoft Visual C++ Redistributable: fai clic per scaricarlo',
        'Windows Firewall blocca il gioco: la cooperativa può fallire (Aiuto)',
    ],
    'pl': [
        'Brakuje Microsoft Visual C++ Redistributable',
        'Potrzebują go pliki AMD FSR 4 i generowania klatek dla DirectX 12. Bez niego Windows nie może ich '
        'wczytać, a launcher pokazuje je jako niedostępne.',
        'Pobierz go od Microsoftu (przycisk poniżej), uruchom i pozwól mu się zainstalować.',
        'Potem zamknij launcher i uruchom go ponownie.',
        'Folder gry jest w synchronizowanym folderze',
        'OneDrive, Dropbox i Google Drive trzymają pliki tylko online, dopóki nie zostaną otwarte, i blokują je '
        'podczas synchronizacji: gra wtedy zawiesza się przy wczytywaniu albo pokazuje tylko czarny ekran.',
        'Przenieś cały folder gry (ten z eboot.bin) do zwykłego folderu, np. C:\\Games\\CUSA03173.',
        'Potem wybierz go ponownie (przycisk poniżej).',
        'Pliki gry są uszkodzone',
        'Pliki w folderze gry nie są plikami czystej wersji 1.09: kopiowanie lub rozpakowanie się nie udało albo '
        'mod został skopiowany do folderu gry. Gra może wtedy zawieszać się przy wczytywaniu, gubić fragmenty mapy '
        'albo wyłączać się w jednym miejscu.',
        'Rozpakuj ponownie grę podstawową i aktualizację 1.09 do nowego, pustego folderu i skopiuj aktualizację na '
        'grę podstawową.',
        'Albo skopiuj z tego nowego rozpakowania do swojego folderu gry tylko pliki, które wskazuje sprawdzanie.',
        'Mody należą na stronę Mods, nie do folderu gry.',
        'Zapora Windows blokuje grę',
        'Windows zapytał, czy bb-probe.exe może korzystać z sieci, i wybrano Anuluj: teraz blokuje połączenia '
        'przychodzące gry, a przyzwania lub dołączanie do innych mogą się nie udać.',
        'Kliknij przycisk poniżej: otworzy się Zapora Windows Defender z zabezpieczeniami zaawansowanymi.',
        'Reguły przychodzące: usuń reguły o nazwie bb-probe.exe z czerwonym znakiem (prawy przycisk > Usuń).',
        'Uruchom grę online i gdy Windows zapyta ponownie, kliknij Zezwalaj.',
        'Pobierz od Microsoftu',
        'Sprawdź pliki gry',
        'Otwórz ustawienia zapory',
        'eboot.bin nie był czystym plikiem 1.09: teraz używana jest czysta kopia z {0}, poprzedni zachowano jako '
        '{1}.',
        '{0} plików gry OneDrive lub inny program chmurowy trzyma tylko online, np. {1}: gra zawiesza się, gdy je '
        'wczytuje.',
        'Folder gry jest w synchronizowanym folderze: {}.',
        'Zapora Windows blokuje połączenia przychodzące gry: kooperacja może się nie udać.',
        'Nie udało się wczytać plików AMD FSR 4: brakuje Microsoft Visual C++ Redistributable ({}).',
        '{0} nie jest używana: jej sterownikowi brakuje {1}, więc gra działa na {2}, dużo wolniej. Zainstaluj '
        'aktualny sterownik dla {0} (czysta instalacja), a potem uruchom ponownie PC.',
        'Nie wybrano jeszcze folderu gry.',
        'Sprawdzanie plików gry… {}%',
        'Wszystkie {} pliki gry są plikami czystej wersji 1.09.',
        '{0} z {1} plików gry różni się od czystej wersji 1.09 lub ich brakuje, np.: {2}. Zobacz „Pliki gry są '
        'uszkodzone” poniżej.',
        'Porównuje każdy plik z czystą wersją 1.09 (kilka minut).',
        '{} nie jest używana: jej sterownik jest za stary dla portu (Pomoc)',
        'Folder gry jest w OneDrive lub innym synchronizowanym folderze: przenieś go (Pomoc)',
        'AMD FSR 4 potrzebuje Microsoft Visual C++ Redistributable: kliknij, aby pobrać',
        'Zapora Windows blokuje grę: kooperacja może się nie udać (Pomoc)',
    ],
    'tr': [
        'Microsoft Visual C++ Redistributable eksik',
        'DirectX 12 için AMD FSR 4 ve kare oluşturma dosyaları buna ihtiyaç duyar. Olmadan Windows onları '
        'yükleyemez ve başlatıcı onları kullanılamaz olarak gösterir.',
        'Microsoft\'tan indirin (aşağıdaki düğme), çalıştırın ve kurulmasına izin verin.',
        'Sonra başlatıcıyı kapatıp yeniden açın.',
        'Oyun klasörü eşitlenen bir klasörde',
        'OneDrive, Dropbox ve Google Drive dosyaları açılana kadar yalnızca çevrimiçi tutar ve eşitleme sırasında '
        'kilitler: oyun o zaman yüklenirken takılır veya yalnızca siyah ekran gösterir.',
        'Oyun klasörünün tamamını (eboot.bin olanı) C:\\Games\\CUSA03173 gibi normal bir klasöre taşıyın.',
        'Sonra onu yeniden seçin (aşağıdaki düğme).',
        'Oyun dosyaları hasarlı',
        'Oyun klasöründeki dosyalar temiz 1.09 dosyaları değil: ters giden bir kopyalama veya ayıklama ya da oyun '
        'klasörüne kopyalanmış bir mod. Oyun o zaman yüklenirken takılabilir, haritanın parçalarını kaybedebilir '
        'veya tek bir yerde çökebilir.',
        'Ana oyunu ve 1.09 güncellemesini yeni, boş bir klasöre yeniden ayıklayın ve güncellemeyi ana oyunun '
        'üzerine kopyalayın.',
        'Ya da o yeni ayıklamadan oyun klasörünüze yalnızca denetimin belirttiği dosyaları kopyalayın.',
        'Modlar oyun klasörüne değil, Mods sayfasına aittir.',
        'Windows Güvenlik Duvarı oyunu engelliyor',
        'Windows, bb-probe.exe\'nin ağı kullanıp kullanamayacağını sordu ve yanıt İptal oldu: artık oyunun gelen '
        'bağlantılarını engelliyor; çağırmalar veya başkalarına katılmak başarısız olabilir.',
        'Aşağıdaki düğmeye tıklayın: Gelişmiş Güvenlik Özellikli Windows Defender Güvenlik Duvarı açılır.',
        'Gelen Kuralları: kırmızı işaretli, bb-probe.exe adlı kuralları silin (sağ tık > Sil).',
        'Oyunu çevrimiçi başlatın ve Windows yeniden sorduğunda İzin ver\'e tıklayın.',
        'Microsoft\'tan indir',
        'Oyun dosyalarını denetle',
        'Güvenlik duvarı ayarlarını aç',
        'eboot.bin temiz 1.09 dosyası değildi: artık {0} içindeki temiz kopya kullanılıyor, diğeri {1} olarak '
        'saklandı.',
        'Oyunun {0} dosyasını OneDrive veya başka bir bulut programı yalnızca çevrimiçi tutuyor, örneğin {1}: oyun '
        'onları yüklerken takılır.',
        'Oyun klasörü eşitlenen bir klasörde: {}.',
        'Windows Güvenlik Duvarı oyunun gelen bağlantılarını engelliyor: ortak oyun başarısız olabilir.',
        'AMD FSR 4 dosyaları yüklenemedi: Microsoft Visual C++ Redistributable eksik ({}).',
        '{0} kullanılmıyor: sürücüsünde {1} eksik; bu yüzden oyun {2} üzerinde, çok daha yavaş çalışıyor. {0} için '
        'güncel sürücüyü kurun (temiz kurulum), ardından bilgisayarı yeniden başlatın.',
        'Henüz oyun klasörü seçilmedi.',
        'Oyun dosyaları denetleniyor… %{}',
        'Oyunun {} dosyasının tümü temiz 1.09 dosyaları.',
        'Oyunun {1} dosyasından {0} tanesi temiz 1.09\'dan farklı veya eksik, örneğin: {2}. Aşağıdaki "Oyun '
        'dosyaları hasarlı" konusuna bakın.',
        'Her dosyayı temiz 1.09 ile karşılaştırır (birkaç dakika).',
        '{} kullanılmıyor: sürücüsü port için fazla eski (Yardım)',
        'Oyun klasörü OneDrive\'da veya eşitlenen başka bir klasörde: taşıyın (Yardım)',
        'AMD FSR 4 için Microsoft Visual C++ Redistributable gerekir: indirmek için tıklayın',
        'Windows Güvenlik Duvarı oyunu engelliyor: ortak oyun başarısız olabilir (Yardım)',
    ],
    'zh': [
        '缺少 Microsoft Visual C++ Redistributable',
        'DirectX 12 版的 AMD FSR 4 和帧生成文件需要它。没有它，Windows 无法加载这些文件，启动器会将其显示为不可用。',
        '从 Microsoft 下载（下方按钮），运行并让它完成安装。',
        '然后关闭启动器并重新打开。',
        '游戏文件夹位于同步文件夹中',
        'OneDrive、Dropbox 和 Google Drive 会在文件被打开前只把它们保存在云端，并在同步时锁定文件：游戏会在加载时卡住，'
        '或只显示黑屏。',
        '把整个游戏文件夹（包含 eboot.bin 的那个）移到普通文件夹，例如 C:\\Games\\CUSA03173。',
        '然后重新选择它（下方按钮）。',
        '游戏文件已损坏',
        '游戏文件夹中的文件不是纯净 1.09 的文件：复制或解包出了问题，或者有模组被复制进了游戏文件夹。游戏可能在加载时卡住、'
        '丢失部分地图，或总在同一处崩溃。',
        '把本体游戏和 1.09 更新重新解包到一个新的空文件夹，并把更新覆盖到本体游戏上。',
        '或者只把检查列出的文件从新解包中复制到你的游戏文件夹。',
        '模组应放在“Mods”页面，而不是游戏文件夹。',
        'Windows 防火墙阻止了游戏',
        'Windows 曾询问 bb-probe.exe 是否可以使用网络，而回答是“取消”：现在它会阻止游戏的传入连接，召唤或加入他人可能失败。',
        '点击下方按钮：将打开“高级安全 Windows Defender 防火墙”。',
        '入站规则：删除名为 bb-probe.exe 且带红色标志的规则（右键 > 删除）。',
        '在线启动游戏，当 Windows 再次询问时点击“允许”。',
        '从 Microsoft 下载',
        '检查游戏文件',
        '打开防火墙设置',
        'eboot.bin 不是纯净的 1.09 文件：现在使用来自 {0} 的纯净副本，原文件保留为 {1}。',
        '有 {0} 个游戏文件被 OneDrive 或其他云程序只保存在云端，例如 {1}：游戏加载它们时会卡住。',
        '游戏文件夹位于同步文件夹中：{}。',
        'Windows 防火墙阻止了游戏的传入连接：联机合作可能失败。',
        '无法加载 AMD FSR 4 文件：缺少 Microsoft Visual C++ Redistributable（{}）。',
        '{0} 未被使用：它的驱动缺少 {1}，所以游戏在 {2} 上运行，慢得多。请安装 {0} 的最新驱动（清洁安装），然后重启电脑。',
        '尚未选择游戏文件夹。',
        '正在检查游戏文件… {}%',
        '全部 {} 个游戏文件都是纯净 1.09 的文件。',
        '{1} 个游戏文件中有 {0} 个与纯净 1.09 不同或缺失，例如：{2}。见下方“游戏文件已损坏”。',
        '将每个文件与纯净 1.09 比较（需要几分钟）。',
        '{} 未被使用：它的驱动对本移植来说太旧（帮助）',
        '游戏文件夹位于 OneDrive 或其他同步文件夹中：请移走它（帮助）',
        'AMD FSR 4 需要 Microsoft Visual C++ Redistributable：点击下载',
        'Windows 防火墙阻止了游戏：联机合作可能失败（帮助）',
    ],
    'ja': [
        'Microsoft Visual C++ 再頒布可能パッケージがありません',
        'DirectX 12 用の AMD FSR 4 とフレーム生成のファイルに必要です。ないと Windows はそれらを読み込めず、ランチャーは'
        '利用不可と表示します。',
        'Microsoft からダウンロードし（下のボタン）、実行してインストールさせてください。',
        'その後ランチャーを閉じて、もう一度起動してください。',
        'ゲームフォルダーが同期フォルダーにあります',
        'OneDrive、Dropbox、Google Drive は開かれるまでファイルをオンラインにだけ置き、同期中はロックします：ゲームは'
        '読み込み中に止まるか、黒い画面しか表示しません。',
        'ゲームフォルダー全体（eboot.bin があるもの）を C:\\Games\\CUSA03173 のような普通のフォルダーに移動してください。',
        'その後もう一度選んでください（下のボタン）。',
        'ゲームファイルが破損しています',
        'ゲームフォルダーのファイルが無改変の 1.09 のものではありません：コピーや展開の失敗、またはゲームフォルダーに'
        'コピーされた Mod です。ゲームが読み込み中に止まったり、マップの一部が消えたり、同じ場所でクラッシュしたりします。',
        'ベースゲームと 1.09 アップデートを新しい空のフォルダーにもう一度展開し、アップデートをベースゲームに上書きコピー'
        'してください。',
        'または、チェックが示したファイルだけをその新しい展開からゲームフォルダーにコピーしてください。',
        'Mod はゲームフォルダーではなく Mods ページに入れます。',
        'Windows ファイアウォールがゲームをブロックしています',
        'bb-probe.exe がネットワークを使ってよいか Windows が尋ねたとき「キャンセル」と答えたため、ゲームへの着信接続が'
        'ブロックされ、召喚や他のプレイヤーへの参加が失敗することがあります。',
        '下のボタンをクリック：セキュリティが強化された Windows Defender ファイアウォールが開きます。',
        '受信の規則：赤いマークの付いた bb-probe.exe という名前の規則を削除してください（右クリック > 削除）。',
        'ゲームをオンラインで起動し、Windows がもう一度尋ねたら「許可」をクリックしてください。',
        'Microsoft からダウンロード',
        'ゲームファイルをチェック',
        'ファイアウォールの設定を開く',
        'eboot.bin は無改変の 1.09 ファイルではありませんでした：{0} の無改変コピーを使用し、元のファイルは {1} として'
        '残しています。',
        'ゲームの {0} 個のファイルが OneDrive などのクラウドプログラムによりオンラインにだけ置かれています（例：{1}）：'
        'ゲームはそれを読み込むときに止まります。',
        'ゲームフォルダーが同期フォルダーにあります：{}。',
        'Windows ファイアウォールがゲームへの着信接続をブロックしています：協力プレイが失敗することがあります。',
        'AMD FSR 4 のファイルを読み込めませんでした：Microsoft Visual C++ 再頒布可能パッケージがありません（{}）。',
        '{0} は使われていません：ドライバーに {1} がないため、ゲームは {2} でずっと遅く動作しています。{0} の最新'
        'ドライバーをインストールし（クリーンインストール）、PC を再起動してください。',
        'ゲームフォルダーがまだ選ばれていません。',
        'ゲームファイルをチェック中… {}%',
        '{} 個のゲームファイルはすべて無改変の 1.09 のものです。',
        '{1} 個中 {0} 個のゲームファイルが無改変の 1.09 と異なるか見つかりません（例：{2}）。下の「ゲームファイルが'
        '破損しています」を参照してください。',
        'すべてのファイルを無改変の 1.09 と比較します（数分）。',
        '{} が使われていません：ドライバーが移植版には古すぎます（ヘルプ）',
        'ゲームフォルダーが OneDrive などの同期フォルダーにあります：移動してください（ヘルプ）',
        'AMD FSR 4 には Microsoft Visual C++ 再頒布可能パッケージが必要です：クリックしてダウンロード',
        'Windows ファイアウォールがゲームをブロックしています：協力プレイが失敗することがあります（ヘルプ）',
    ],
    'ko': [
        'Microsoft Visual C++ 재배포 가능 패키지가 없습니다',
        'DirectX 12용 AMD FSR 4와 프레임 생성 파일에 필요합니다. 없으면 Windows가 이 파일을 불러올 수 없고, 런처는 '
        '사용할 수 없다고 표시합니다.',
        'Microsoft에서 내려받아(아래 버튼) 실행하고 설치되게 하세요.',
        '그런 다음 런처를 닫고 다시 시작하세요.',
        '게임 폴더가 동기화 폴더에 있습니다',
        'OneDrive, Dropbox, Google Drive는 파일을 열기 전까지 온라인에만 두고, 동기화하는 동안 잠급니다: 그러면 게임이 '
        '로딩 중에 멈추거나 검은 화면만 보입니다.',
        '게임 폴더 전체(eboot.bin이 있는 폴더)를 C:\\Games\\CUSA03173 같은 일반 폴더로 옮기세요.',
        '그런 다음 다시 선택하세요(아래 버튼).',
        '게임 파일이 손상되었습니다',
        '게임 폴더의 파일이 깨끗한 1.09의 파일이 아닙니다: 복사나 압축 해제가 잘못되었거나, 모드가 게임 폴더에 복사되었습니다. '
        '그러면 게임이 로딩 중에 멈추거나, 맵 일부가 사라지거나, 한 곳에서 튕길 수 있습니다.',
        '기본 게임과 1.09 업데이트를 새 빈 폴더에 다시 압축 해제하고, 업데이트를 기본 게임 위에 복사하세요.',
        '또는 검사가 알려 준 파일만 새로 압축 해제한 곳에서 게임 폴더로 복사하세요.',
        '모드는 게임 폴더가 아니라 Mods 페이지에 넣습니다.',
        'Windows 방화벽이 게임을 차단합니다',
        'Windows가 bb-probe.exe의 네트워크 사용을 허용할지 물었을 때 취소를 눌렀습니다: 이제 게임의 들어오는 연결이 '
        '차단되어 소환이나 다른 사람 세계 참가가 실패할 수 있습니다.',
        '아래 버튼을 클릭하세요: 고급 보안이 포함된 Windows Defender 방화벽이 열립니다.',
        '인바운드 규칙: 빨간 표시가 있는 bb-probe.exe라는 규칙을 삭제하세요(오른쪽 클릭 > 삭제).',
        '게임을 온라인으로 시작하고 Windows가 다시 물으면 허용을 클릭하세요.',
        'Microsoft에서 내려받기',
        '게임 파일 검사',
        '방화벽 설정 열기',
        'eboot.bin이 깨끗한 1.09 파일이 아니었습니다: 이제 {0}의 깨끗한 사본을 사용하며, 기존 파일은 {1}(으)로 '
        '보관됩니다.',
        '게임 파일 {0}개를 OneDrive 또는 다른 클라우드 프로그램이 온라인에만 두고 있습니다(예: {1}): 게임이 이 파일을 '
        '불러올 때 멈춥니다.',
        '게임 폴더가 동기화 폴더에 있습니다: {}.',
        'Windows 방화벽이 게임의 들어오는 연결을 차단합니다: 협동 플레이가 실패할 수 있습니다.',
        'AMD FSR 4 파일을 불러오지 못했습니다: Microsoft Visual C++ 재배포 가능 패키지가 없습니다({}).',
        '{0}이(가) 사용되지 않음: 드라이버에 {1}이(가) 없어 게임이 {2}에서 훨씬 느리게 실행됩니다. {0}의 최신 드라이버를 '
        '설치(클린 설치)한 뒤 PC를 다시 시작하세요.',
        '아직 게임 폴더를 선택하지 않았습니다.',
        '게임 파일 검사 중… {}%',
        '게임 파일 {}개가 모두 깨끗한 1.09의 파일입니다.',
        '게임 파일 {1}개 중 {0}개가 깨끗한 1.09와 다르거나 없습니다(예: {2}). 아래의 "게임 파일이 손상되었습니다"를 '
        '보세요.',
        '모든 파일을 깨끗한 1.09와 비교합니다(몇 분).',
        '{}이(가) 사용되지 않음: 드라이버가 포트에 비해 너무 오래됨 (도움말)',
        '게임 폴더가 OneDrive 또는 다른 동기화 폴더에 있음: 옮기세요 (도움말)',
        'AMD FSR 4에는 Microsoft Visual C++ 재배포 가능 패키지가 필요합니다: 클릭해서 내려받기',
        'Windows 방화벽이 게임을 차단함: 협동 플레이가 실패할 수 있음 (도움말)',
    ],
}

for _language, _texts in TEXTS.items():
    assert len(_texts) == len(KEYS), (_language, len(_texts), len(KEYS))
    bbport_lang.EXTRA_TRANSLATIONS.setdefault(_language, {}).update(zip(KEYS, _texts))
