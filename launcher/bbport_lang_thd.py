# SPDX-License-Identifier: GPL-2.0-or-later
"""1.9.7's notice: The Hunter's Dream is no longer offered (HUNTERS_DREAM_POOL off), in every language besides
English. Keyed by the English text like bbport_lang; merged into its tables on import."""
import bbport_lang

KEYS = [
    "The Hunter's Dream is no longer offered: the port plays on SuperMedo Server only. If you played there, you "
    'now play on SuperMedo Server. Sign in, or make a free account, on the Online page.',
]
TEXTS = {
    'ru': ["The Hunter's Dream больше не предлагается: порт играет только на SuperMedo Server. Если вы играли там, "
           'теперь вы играете на SuperMedo Server. Войдите или создайте бесплатный аккаунт на странице «Онлайн».'],
    'ar': ['لم يعد The Hunter\'s Dream متاحًا: يعمل المنفذ على خادم SuperMedo فقط. إذا كنت تلعب هناك، فأنت الآن '
           'تلعب على خادم SuperMedo. سجّل الدخول أو أنشئ حسابًا مجانيًا في صفحة الاتصال بالإنترنت.'],
    'es': ["The Hunter's Dream ya no se ofrece: el port solo juega en SuperMedo Server. Si jugabas allí, ahora "
           'juegas en SuperMedo Server. Inicia sesión o crea una cuenta gratis en la página En línea.'],
    'pt': ["The Hunter's Dream não é mais oferecido: o port joga apenas no SuperMedo Server. Se você jogava lá, agora "
           'joga no SuperMedo Server. Entre ou crie uma conta grátis na página Online.'],
    'fr': ["The Hunter's Dream n'est plus proposé : le port joue uniquement sur SuperMedo Server. Si vous y jouiez, "
           'vous jouez maintenant sur SuperMedo Server. Connectez-vous ou créez un compte gratuit sur la page En ligne.'],
    'de': ["The Hunter's Dream wird nicht mehr angeboten: Der Port spielt nur noch auf SuperMedo Server. Wenn du dort "
           'gespielt hast, spielst du jetzt auf SuperMedo Server. Melde dich auf der Seite „Online“ an oder erstelle '
           'dort ein kostenloses Konto.'],
    'it': ["The Hunter's Dream non è più disponibile: il port gioca solo su SuperMedo Server. Se giocavi lì, ora "
           'giochi su SuperMedo Server. Accedi o crea un account gratuito nella pagina Online.'],
    'pl': ["The Hunter's Dream nie jest już dostępny: port gra tylko na SuperMedo Server. Jeśli tam grałeś, teraz "
           'grasz na SuperMedo Server. Zaloguj się lub załóż darmowe konto na stronie Online.'],
    'tr': ["The Hunter's Dream artık sunulmuyor: port yalnızca SuperMedo Server'da oynuyor. Orada oynadıysan artık "
           "SuperMedo Server'da oynuyorsun. Çevrimiçi sayfasında giriş yap veya ücretsiz bir hesap oluştur."],
    'zh': ["不再提供 The Hunter's Dream：本移植版现在只使用 SuperMedo Server。如果你之前在那里游玩，现在会在 "
           'SuperMedo Server 上游玩。请在“在线”页面登录或创建免费账号。'],
    'ja': ["The Hunter's Dream は提供を終了しました。移植版は SuperMedo Server のみで遊びます。そちらで遊んでいた場合は、"
           '今後は SuperMedo Server で遊びます。「オンライン」ページでサインインするか、無料アカウントを作成してください。'],
    'ko': ["The Hunter's Dream은 더 이상 제공되지 않습니다. 이제 포트는 SuperMedo Server에서만 플레이합니다. 그곳에서 "
           '플레이했다면 이제 SuperMedo Server에서 플레이합니다. 온라인 페이지에서 로그인하거나 무료 계정을 만드세요.'],
}

for _language, _texts in TEXTS.items():
    assert len(_texts) == len(KEYS), (_language, len(_texts), len(KEYS))
    bbport_lang.EXTRA_TRANSLATIONS.setdefault(_language, {}).update(zip(KEYS, _texts))
