# SPDX-License-Identifier: GPL-2.0-or-later
"""Localized labels for the Workshop tools on the upstream launcher pages."""

KEYS = (
    'Workshop snapshots',
    'Open Save Manager…',
    'Automatic snapshots are kept in Save Manager. Use Backup options there to set retention.',
    'Legacy backups and import',
    'Generate Support Report…',
)
TEXTS = {
    'ru': (
        'Снимки Workshop', 'Открыть менеджер сохранений…',
        'Автоматические снимки находятся в менеджере сохранений. Срок хранения задаётся в параметрах копирования.',
        'Старые резервные копии и импорт', 'Создать отчёт…',
    ),
    'ar': (
        'لقطات Workshop', 'فتح مدير الحفظ…',
        'تُحفظ اللقطات التلقائية في مدير الحفظ. اضبط مدة الاحتفاظ بها في خيارات النسخ الاحتياطي.',
        'النسخ الاحتياطية القديمة والاستيراد', 'إنشاء تقرير دعم…',
    ),
    'es': (
        'Instantáneas de Workshop', 'Abrir el gestor de partidas…',
        'Las instantáneas automáticas están en el gestor de partidas. Configura su conservación en las opciones de copia.',
        'Copias antiguas e importación', 'Generar informe de soporte…',
    ),
    'pt': (
        'Cópias do Workshop', 'Abrir o gerenciador de saves…',
        'As cópias automáticas ficam no gerenciador de saves. Defina a retenção nas opções de backup.',
        'Backups antigos e importação', 'Gerar relatório de suporte…',
    ),
    'fr': (
        'Instantanés de Workshop', 'Ouvrir le gestionnaire de sauvegardes…',
        'Les instantanés automatiques sont dans le gestionnaire. Réglez leur conservation dans les options de sauvegarde.',
        'Anciennes sauvegardes et importation', 'Générer un rapport de diagnostic…',
    ),
    'de': (
        'Workshop-Sicherungen', 'Spielstandverwaltung öffnen…',
        'Automatische Sicherungen findest du in der Spielstandverwaltung. Die Aufbewahrung stellst du dort in den Sicherungsoptionen ein.',
        'Ältere Sicherungen und Import', 'Supportbericht erstellen…',
    ),
    'it': (
        'Backup di Workshop', 'Apri gestione salvataggi…',
        'I backup automatici si trovano nella gestione salvataggi. Puoi scegliere quanti conservarne nelle opzioni di backup.',
        'Backup precedenti e importazione', 'Genera rapporto di assistenza…',
    ),
    'pl': (
        'Migawki Workshop', 'Otwórz menedżer zapisów…',
        'Automatyczne migawki są w menedżerze zapisów. Zmień zasady ich przechowywania w opcjach kopii zapasowych.',
        'Starsze kopie i importowanie', 'Utwórz raport pomocy technicznej…',
    ),
    'tr': (
        'Workshop anlık kopyaları', 'Kayıt yöneticisini aç…',
        'Otomatik kopyalar kayıt yöneticisinde tutulur. Saklama ayarını yedekleme seçeneklerinden değiştir.',
        'Eski yedekler ve içe aktarma', 'Destek raporu oluştur…',
    ),
    'zh': (
        'Workshop 存档快照', '打开存档管理器…',
        '自动快照保存在存档管理器中。可在备份选项中设置保留数量。',
        '旧版备份和导入', '生成支持报告…',
    ),
    'ja': (
        'Workshop のスナップショット', 'セーブ管理を開く…',
        '自動スナップショットはセーブ管理に保存されます。バックアップ設定で保持数を変更できます。',
        '旧形式のバックアップとインポート', 'サポートレポートを作成…',
    ),
    'ko': (
        'Workshop 스냅샷', '저장 데이터 관리자 열기…',
        '자동 스냅샷은 저장 데이터 관리자에 보관됩니다. 백업 옵션에서 보관 개수를 설정할 수 있습니다.',
        '이전 백업 및 가져오기', '지원 보고서 만들기…',
    ),
}
TRANSLATIONS = {lang: dict(zip(KEYS, texts, strict=True)) for lang, texts in TEXTS.items()}
