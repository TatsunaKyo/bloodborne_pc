# SPDX-License-Identifier: GPL-2.0-or-later
"""The texts of the background work that no longer ends without a word (the launcher check of 30.10.2026, item 3):
a check of the graphics card that stopped, an account the server could not make, last_run.log on a full drive, the
shader cache while a game runs or when part of it stays, and Add to Steam clicked again while it waits for Steam. In
every language besides English; keyed by the English text like bbport_lang, merged into its tables on import."""
import bbport_lang

KEYS = [
    'The check of the graphics card stopped: {}',
    'The account could not be created: {}',
    "{0} could not be written ({1}): the rest of this game's log is only on this page.",
    'Close the game first: it uses the shader cache while it runs.',
    'Part of the shader cache could not be deleted: {}',
    'Bloodborne is still being added to Steam: Steam closes for it first, which can take up to half a minute.',
]

TEXTS = {
    'ru': [
        'Проверка видеокарты прервана: {}',
        'Не удалось создать аккаунт: {}',
        'Не удалось записать {0} ({1}): остальной журнал этой игры есть только на этой странице.',
        'Сначала закройте игру: пока она запущена, она использует кэш шейдеров.',
        'Часть кэша шейдеров не удалось удалить: {}',
        'Bloodborne ещё добавляется в Steam: сначала Steam закрывается, это может занять до полминуты.',
    ],
    'ar': [
        'توقف فحص بطاقة الرسوميات: {}',
        'تعذّر إنشاء الحساب: {}',
        'تعذّرت الكتابة إلى {0} ({1}): بقية سجل هذه اللعبة موجودة في هذه الصفحة فقط.',
        'أغلق اللعبة أولًا؛ فهي تستخدم كاش الشيدر أثناء تشغيلها.',
        'تعذّر حذف جزء من كاش الشيدر: {}',
        'لا تزال إضافة Bloodborne إلى Steam جارية: يُغلق Steam أولًا، وقد يستغرق ذلك حتى نصف دقيقة.',
    ],
    'es': [
        'La comprobación de la tarjeta gráfica se detuvo: {}',
        'No se pudo crear la cuenta: {}',
        'No se pudo escribir {0} ({1}): el resto del registro de esta partida solo está en esta página.',
        'Primero cierra el juego: usa la caché de shaders mientras está en marcha.',
        'No se pudo borrar parte de la caché de shaders: {}',
        'Bloodborne todavía se está añadiendo a Steam: antes Steam se cierra, lo que puede tardar hasta medio minuto.',
    ],
    'pt': [
        'A verificação da placa de vídeo parou: {}',
        'Não foi possível criar a conta: {}',
        'Não foi possível gravar {0} ({1}): o resto do registro deste jogo está só nesta página.',
        'Feche o jogo primeiro: ele usa o cache de shaders enquanto está rodando.',
        'Parte do cache de shaders não pôde ser apagada: {}',
        'O Bloodborne ainda está sendo adicionado à Steam: antes a Steam fecha, o que pode levar até meio minuto.',
    ],
    'fr': [
        'La vérification de la carte graphique s’est arrêtée : {}',
        'Impossible de créer le compte : {}',
        'Impossible d’écrire {0} ({1}) : la suite du journal de cette partie n’est que sur cette page.',
        'Fermez d’abord le jeu : il utilise le cache des shaders tant qu’il tourne.',
        'Une partie du cache des shaders n’a pas pu être supprimée : {}',
        'Bloodborne est encore en cours d’ajout à Steam : Steam se ferme d’abord, ce qui peut prendre jusqu’à '
        'une demi-minute.',
    ],
    'de': [
        'Die Prüfung der Grafikkarte brach ab: {}',
        'Das Konto konnte nicht angelegt werden: {}',
        '{0} konnte nicht geschrieben werden ({1}): Der Rest des Protokolls dieses Spiels steht nur auf dieser Seite.',
        'Schließe zuerst das Spiel: Es benutzt den Shader-Cache, solange es läuft.',
        'Ein Teil des Shader-Caches konnte nicht gelöscht werden: {}',
        'Bloodborne wird noch zu Steam hinzugefügt: Dafür schließt sich Steam zuerst, das kann bis zu einer halben '
        'Minute dauern.',
    ],
    'it': [
        'La verifica della scheda video si è interrotta: {}',
        'Impossibile creare l’account: {}',
        'Impossibile scrivere {0} ({1}): il resto del registro di questa partita è solo in questa pagina.',
        'Chiudi prima il gioco: usa la cache degli shader mentre è in esecuzione.',
        'Non è stato possibile eliminare parte della cache degli shader: {}',
        'Bloodborne è ancora in fase di aggiunta a Steam: prima Steam si chiude, e può volerci fino a mezzo minuto.',
    ],
    'pl': [
        'Sprawdzanie karty graficznej przerwane: {}',
        'Nie udało się utworzyć konta: {}',
        'Nie można zapisać {0} ({1}): reszta dziennika tej gry jest tylko na tej stronie.',
        'Najpierw zamknij grę: podczas działania używa ona pamięci shaderów.',
        'Nie udało się usunąć części pamięci shaderów: {}',
        'Bloodborne jest wciąż dodawany do Steam: najpierw Steam się zamyka, co może potrwać do pół minuty.',
    ],
    'tr': [
        'Ekran kartı kontrolü durdu: {}',
        'Hesap oluşturulamadı: {}',
        '{0} yazılamadı ({1}): bu oyunun günlüğünün geri kalanı yalnızca bu sayfada.',
        'Önce oyunu kapatın: oyun çalışırken shader önbelleğini kullanır.',
        'Shader önbelleğinin bir kısmı silinemedi: {}',
        "Bloodborne hâlâ Steam'e ekleniyor: önce Steam kapanır, bu yarım dakikaya kadar sürebilir.",
    ],
    'zh': [
        '显卡检查已中止：{}',
        '无法创建账户：{}',
        '无法写入 {0}（{1}）：本次游戏日志的其余部分只在此页面上。',
        '请先关闭游戏：游戏运行时会使用着色器缓存。',
        '部分着色器缓存无法删除：{}',
        'Bloodborne 仍在添加到 Steam：Steam 需要先关闭，最多可能需要半分钟。',
    ],
    'ja': [
        'グラフィックカードの確認が中断されました：{}',
        'アカウントを作成できませんでした：{}',
        '{0} に書き込めませんでした（{1}）：このゲームのログの残りはこのページにのみ表示されます。',
        '先にゲームを終了してください。ゲームは実行中にシェーダーキャッシュを使用します。',
        'シェーダーキャッシュの一部を削除できませんでした：{}',
        'Bloodborne を Steam に追加しています。先に Steam が終了するため、最大 30 秒ほどかかることがあります。',
    ],
    'ko': [
        '그래픽 카드 검사 중단: {}',
        '계정을 만들 수 없습니다: {}',
        '{0}에 기록할 수 없습니다({1}): 이 게임 로그의 나머지는 이 페이지에만 있습니다.',
        '먼저 게임을 종료하세요. 게임은 실행 중에 셰이더 캐시를 사용합니다.',
        '셰이더 캐시 일부를 삭제할 수 없습니다: {}',
        'Bloodborne를 아직 Steam에 추가하는 중입니다. 먼저 Steam이 종료되며, 최대 30초 정도 걸릴 수 있습니다.',
    ],
}

for _language, _texts in TEXTS.items():
    assert len(_texts) == len(KEYS), (_language, len(_texts), len(KEYS))
    bbport_lang.EXTRA_TRANSLATIONS.setdefault(_language, {}).update(zip(KEYS, _texts))
