# SPDX-License-Identifier: GPL-2.0-or-later
"""Localized choice of controller or keyboard and mouse (Play, Controls; setting play_with)."""

KEYS = (
    'You play with',
    'Controller',
    'Keyboard and mouse turns the mouse camera on and uses the Dark Souls III layout (asked first if you '
    'changed keys yourself). Controller turns the mouse camera off, so the game leaves the pointer alone. '
    'Keys and controller buttons keep working either way.',
    "You changed the keyboard and mouse bindings yourself. Replace them with the Dark Souls III layout? "
    "The controller's buttons stay.\n\nNo keeps your keys and only turns the mouse camera on.",
)
TEXTS = {
    'en': KEYS,
    'de': (
        'Du spielst mit',
        'Controller',
        'Tastatur und Maus schaltet die Mauskamera ein und nutzt das Dark-Souls-III-Layout (vorher wird '
        'gefragt, wenn du selbst Tasten geändert hast). Controller schaltet die Mauskamera aus, damit das '
        'Spiel den Mauszeiger in Ruhe lässt. Tasten und Controller-Knöpfe funktionieren in beiden Fällen.',
        'Du hast die Tastatur- und Mausbelegung selbst geändert. Durch das Dark-Souls-III-Layout ersetzen? '
        'Die Controller-Knöpfe bleiben.\n\nNein behält deine Tasten und schaltet nur die Mauskamera ein.',
    ),
    'ru': (
        'Устройство ввода',
        'Геймпад',
        'Клавиатура и мышь включают управление камерой мышью и раскладку Dark Souls III (если вы сами '
        'меняли клавиши, сначала будет вопрос). Геймпад выключает управление камерой мышью, чтобы игра не '
        'захватывала указатель. Клавиши и кнопки геймпада работают в обоих случаях.',
        'Вы сами меняли привязки клавиатуры и мыши. Заменить их раскладкой Dark Souls III? Кнопки геймпада '
        'не изменятся.\n\n«Нет» оставит ваши клавиши и только включит управление камерой мышью.',
    ),
    'ar': (
        'تلعب باستخدام',
        'وحدة تحكم',
        'لوحة المفاتيح والماوس تشغّل كاميرا الماوس وتستخدم تخطيط Dark Souls III (مع سؤالك أولًا إذا غيّرت '
        'المفاتيح بنفسك). وحدة التحكم تطفئ كاميرا الماوس كي لا تمسك اللعبة بالمؤشر. تبقى المفاتيح وأزرار '
        'وحدة التحكم تعمل في الحالتين.',
        'لقد غيّرت تعيينات لوحة المفاتيح والماوس بنفسك. هل تستبدلها بتخطيط Dark Souls III؟ تبقى أزرار وحدة '
        'التحكم كما هي.\n\n«لا» يُبقي مفاتيحك ويشغّل كاميرا الماوس فقط.',
    ),
    'es': (
        'Juegas con',
        'Mando',
        'Teclado y ratón activa la cámara de ratón y usa el esquema de Dark Souls III (se pregunta antes si '
        'cambiaste teclas tú mismo). Mando desactiva la cámara de ratón para que el juego no retenga el '
        'puntero. Las teclas y los botones del mando siguen funcionando en ambos casos.',
        'Cambiaste tú mismo las asignaciones de teclado y ratón. ¿Reemplazarlas por el esquema de Dark '
        'Souls III? Los botones del mando no cambian.\n\n«No» mantiene tus teclas y solo activa la cámara '
        'de ratón.',
    ),
    'pt': (
        'Você joga com',
        'Controle',
        'Teclado e mouse liga a câmera pelo mouse e usa o layout do Dark Souls III (com uma pergunta antes '
        'se você mudou teclas). Controle desliga a câmera pelo mouse, para o jogo não prender o ponteiro. '
        'Teclas e botões do controle continuam funcionando nos dois casos.',
        'Você mudou o mapeamento de teclado e mouse. Substituir pelo layout do Dark Souls III? Os botões do '
        'controle continuam como estão.\n\n"Não" mantém suas teclas e só liga a câmera pelo mouse.',
    ),
    'fr': (
        'Vous jouez avec',
        'Manette',
        'Clavier et souris active la caméra à la souris et utilise la disposition Dark Souls III (avec une '
        'question d\'abord si vous avez modifié des touches). Manette désactive la caméra à la souris pour '
        'que le jeu ne capture pas le pointeur. Les touches et les boutons de la manette fonctionnent dans '
        'les deux cas.',
        'Vous avez modifié vous-même les assignations clavier et souris. Les remplacer par la disposition '
        'Dark Souls III ? Les boutons de la manette restent inchangés.\n\n« Non » garde vos touches et active '
        'seulement la caméra à la souris.',
    ),
    'it': (
        'Giochi con',
        'Controller',
        'Tastiera e mouse attiva la telecamera col mouse e usa il layout di Dark Souls III (con una domanda '
        'prima se hai cambiato tu dei tasti). Controller disattiva la telecamera col mouse, così il gioco non '
        'trattiene il puntatore. Tasti e pulsanti del controller funzionano in entrambi i casi.',
        'Hai cambiato tu le assegnazioni di tastiera e mouse. Sostituirle con il layout di Dark Souls III? I '
        'pulsanti del controller restano invariati.\n\n«No» mantiene i tuoi tasti e attiva solo la '
        'telecamera col mouse.',
    ),
    'pl': (
        'Urządzenie do gry',
        'Kontroler',
        'Klawiatura i mysz włącza kamerę sterowaną myszą i układ z Dark Souls III (najpierw pytanie, jeśli '
        'zmieniano klawisze). Kontroler wyłącza kamerę sterowaną myszą, żeby gra nie przechwytywała kursora. '
        'Klawisze i przyciski kontrolera działają w obu przypadkach.',
        'Przypisania klawiatury i myszy zostały przez Ciebie zmienione. Zastąpić je układem z Dark Souls III? '
        'Przyciski kontrolera pozostaną bez zmian.\n\n„Nie” zachowuje Twoje klawisze i tylko włącza kamerę '
        'sterowaną myszą.',
    ),
    'tr': (
        'Giriş cihazı',
        'Kumanda',
        'Klavye ve fare, fare kamerasını açar ve Dark Souls III düzenini kullanır (tuşları kendiniz '
        'değiştirdiyseniz önce sorulur). Kumanda, oyun imleci tutmasın diye fare kamerasını kapatır. Tuşlar '
        've kumanda düğmeleri her iki durumda da çalışır.',
        'Klavye ve fare atamalarını kendiniz değiştirdiniz. Dark Souls III düzeniyle değiştirilsin mi? Kumanda '
        'düğmeleri olduğu gibi kalır.\n\n"Hayır" tuşlarınızı korur ve yalnızca fare kamerasını açar.',
    ),
    'zh': (
        '操作方式',
        '手柄',
        '键盘和鼠标：开启鼠标控制镜头并使用 Dark Souls III 布局（如果你自己改过按键，会先询问）。手柄：关闭'
        '鼠标控制镜头，游戏不再占用鼠标指针。两种情况下按键和手柄按钮都能用。',
        '你自己改过键盘和鼠标绑定。要用 Dark Souls III 布局替换吗？手柄按钮保持不变。\n\n选“否”会保留你的'
        '按键，只开启鼠标控制镜头。',
    ),
    'ja': (
        '操作方法',
        'コントローラー',
        'キーボードとマウスを選ぶとマウスカメラがオンになり、DARK SOULS III 配置を使います（キーを自分で変更'
        'していた場合は先に確認します）。コントローラーを選ぶとマウスカメラがオフになり、ゲームがマウス'
        'ポインターを捕まえなくなります。キーとコントローラーのボタンはどちらの場合も使えます。',
        'キーボードとマウスの割り当てを自分で変更しています。DARK SOULS III 配置に置き換えますか？'
        'コントローラーのボタンはそのままです。\n\n「いいえ」を選ぶとキーはそのままで、マウスカメラだけを'
        'オンにします。',
    ),
    'ko': (
        '조작 방식',
        '컨트롤러',
        '키보드 및 마우스는 마우스 카메라를 켜고 다크 소울 III 배치를 사용합니다(키를 직접 바꿨다면 먼저 '
        '묻습니다). 컨트롤러는 마우스 카메라를 꺼서 게임이 마우스 포인터를 잡지 않게 합니다. 키와 컨트롤러 '
        '버튼은 어느 쪽이든 계속 작동합니다.',
        '키보드 및 마우스 키 지정을 직접 바꾸셨습니다. 다크 소울 III 배치로 바꿀까요? 컨트롤러 버튼은 그대로 '
        '유지됩니다.\n\n"아니요"를 누르면 키는 그대로 두고 마우스 카메라만 켭니다.',
    ),
}
TRANSLATIONS = {language: dict(zip(KEYS, texts, strict=True)) for language, texts in TEXTS.items()}
