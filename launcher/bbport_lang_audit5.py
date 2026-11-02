# SPDX-License-Identifier: GPL-2.0-or-later
"""The texts of Help's new order: the heading of the report and the Discord, above the problems now (it was
"Still stuck?" below them). In every language besides English; keyed by the English text like bbport_lang,
merged into its tables on import."""
import bbport_lang

KEYS = [
    'Ask for help',
]

TEXTS = {
    'ru': ['Обратиться за помощью'],
    'ar': ['اطلب المساعدة'],
    'es': ['Pedir ayuda'],
    'pt': ['Pedir ajuda'],
    'fr': ['Demander de l’aide'],
    'de': ['Um Hilfe bitten'],
    'it': ['Chiedere aiuto'],
    'pl': ['Poproś o pomoc'],
    'tr': ['Yardım isteyin'],
    'zh': ['寻求帮助'],
    'ja': ['助けを求める'],
    'ko': ['도움 요청하기'],
}

for _language, _texts in TEXTS.items():
    assert len(_texts) == len(KEYS), (_language, len(_texts), len(KEYS))
    bbport_lang.EXTRA_TRANSLATIONS.setdefault(_language, {}).update(zip(KEYS, _texts))
