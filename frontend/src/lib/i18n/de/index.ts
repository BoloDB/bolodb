import type { BaseTranslation } from "../i18n-types";

const de = {
  common: {
    appName: "BoloDB",
    tagline: "Fragen Sie Ihre Daten. Vertrauen Sie der Antwort.",
    email: "E-Mail",
    password: "Passwort",
    or: "oder",
    cancel: "Abbrechen",
    save: "Änderungen speichern",
    saving: "Speichern\u2026",
    loading: "Laden\u2026",
    connecting: "Verbinden\u2026",
    remove: "Entfernen",
    change: "Ändern",
    yes: "Ja",
    no: "Nein",
    close: "Schließen",
    justNow: "gerade eben",
    minutesAgo: "vor {n} Min.",
    hoursAgo: "vor {n} Std.",
    daysAgo: "vor {n} Tagen",
    noData: "Noch keine Daten",
    somethingWentWrong:
      "Etwas ist schiefgelaufen — bitte versuchen Sie es erneut.",
  },
  auth: {
    welcomeBack: "Willkommen zurück",
    signInToAccount: "Melden Sie sich bei Ihrem BoloDB-Konto an",
    signIn: "Anmelden",
    signingIn: "Anmelden\u2026",
    emailPlaceholder: "sie@firma.de",
    passwordPlaceholder: "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022",
    pleaseEnterEmailAndPassword: "Bitte E-Mail und Passwort eingeben",
    loginFailed: "Anmeldung fehlgeschlagen",
    noAccount: "Noch kein Konto?",
    signUp: "Registrieren",
    createAccount: "Konto erstellen",
    joinBoloDB: "BoloDB beitreten",
    signUpSuccess: "Konto erstellt!",
    signingUp: "Konto wird erstellt\u2026",
    signupFailed: "Registrierung fehlgeschlagen",
    alreadyHaveAccount: "Bereits ein Konto?",
    continueWithGoogle: "Mit Google fortfahren",
    logOut: "Abmelden",
    passwordMinLength: "Mindestens 8 Zeichen",
    passwordUpperLower: "Groß- und Kleinbuchstaben",
    passwordNumber: "Mindestens eine Zahl",
    passwordSpecial: "Mindestens ein Sonderzeichen",
    passwordChanged: "Passwort erfolgreich geändert",
  },
  landing: {
    talkToYourDatabase: "Sprechen Sie mit Ihrer Datenbank",
    likeAHuman: "wie mit einem Menschen.",
    noSqlRequired:
      "Kein SQL nötig. Stellen Sie Fragen in natürlicher Sprache, erhalten Sie sofort Antworten und vertrauen Sie der Logik mit unserer überprüfbaren KI-Engine.",
    startForFree: "Kostenlos starten",
    viewDemo: "Demo ansehen",
    featureZeroSetupTitle: "Keine Einrichtung",
    featureZeroSetupDesc:
      "Geben Sie einfach Ihre Datenbankverbindungszeichenfolge an. BoloDB leitet automatisch Ihr Schema ab, indiziert Tabellen und ist sofort abfragebereit.",
    featureDataStaysYoursTitle: "Ihre Daten bleiben Ihre",
    featureDataStaysYoursDesc:
      "Nur Ihre Datenbankstruktur und Ihre Frage werden an die KI gesendet — niemals die Zeilen in Ihren Tabellen. Abfragen werden schreibgeschützt ausgeführt.",
    featureTrustEngineTitle: "Vertrauens-Engine",
    featureTrustEngineDesc:
      "Vertrauen Sie nie blind. Sehen Sie das exakte SQL für jede Frage ein. Während Sie Abfragen verifizieren, kalibriert sich die KI auf Ihre spezifische Domäne.",
    copyright: "\u00a9 2026 BoloDB. Alle Rechte vorbehalten.",
    demoTitle: "bolodb-chat-demo",
  },
  nav: {
    chat: "Chat",
    dashboard: "Dashboard",
    connect: "Verbinden",
    toggleTheme: "Design umschalten",
  },
  connect: {
    askYourData: "Fragen Sie Ihre Daten in natürlicher Sprache.",
    trust: "Vertrauen",
    theAnswerYouGetBack: "der Antwort, die Sie erhalten.",
    pickWhereAiRuns:
      "Wählen Sie, wo die KI läuft, verbinden Sie Ihre Datenbank und stellen Sie Fragen — kein SQL-Wissen erforderlich.",
    recentDatabases: "Letzte Datenbanken",
    pickUpWhereYouLeft: "Machen Sie weiter, wo Sie aufgehört haben",
    connect: "Verbinden",
    connecting: "Verbinden\u2026",
    reconnecting: "Erneut verbinden\u2026",
    removeFromRecent: "Aus letzen entfernen",
    setUpAi: "KI einrichten",
    setUpAiHint:
      "BoloDB verwendet OpenRouter, um Ihre Fragen in Datenbankabfragen umzuwandeln. Sie benötigen nur einen kostenlosen API-Schlüssel.",
    openrouterKeyConfigured:
      "OpenRouter-API-Schlüssel konfiguriert — die KI ist bereit.",
    changeKey: "Schlüssel ändern",
    getFreeKey: "Kostenlosen API-Schlüssel erhalten von",
    googleAiStudio: "Google AI Studio \u2192",
    signInWithGoogle:
      '(mit einem Google-Konto anmelden, auf "Create API key" klicken, kopieren) und unten einfügen.',
    saveKey: "Schlüssel speichern",
    saving: "Speichern\u2026",
    cancelKeepKey: "\u2190 Abbrechen, vorhandenen Schlüssel behalten",
    privacyNotice:
      "Selbst mit einer Cloud-Engine werden nur Ihre Datenbankstruktur und Ihre Frage gesendet — niemals Ihre tatsächlichen Datenzeilen.",
    privacyShort:
      "Nur das Schema und Ihre Frage werden an OpenRouter gesendet, um SQL zu generieren — niemals Ihre Zeilendaten.",
    connectDatabase: "Datenbank verbinden",
    connectDatabaseHint:
      "Noch keine? Verwenden Sie zuerst die Beispieldaten, um zu sehen, wie es funktioniert.",
    yourDatabase: "Ihre Datenbank",
    whatTypeOfDb: "Welcher Datenbanktyp?",
    filePath: "Dateipfad",
    host: "Host",
    port: "Port",
    username: "Benutzername",
    password: "Passwort",
    databaseName: "Datenbankname",
    connectionUrl: "Verbindungs-URL",
    backToSimpleForm: "\u2190 Zurück zum einfachen Formular",
    useFullUrl: "Vollständige Verbindungs-URL? Dann diese verwenden \u2192",
    connectDatabaseBtn: "Datenbank verbinden",
    viewOnlyTip:
      "Tipp: Verwenden Sie ein schreibgeschütztes Datenbankkonto — BoloDB schreibt nie in Ihre Daten.",
    trySampleData: "Mit Beispieldaten testen",
    buildingSample: "Beispieldaten werden erstellt\u2026",
    sampleDataDesc:
      "Eine realistische TechStore-E-Commerce-Datenbank, lokal für Sie erstellt. Keine Einrichtung, keine Anmeldedaten, in Sekunden bereit.",
    startInSeconds: "In Sekunden starten",
    couldNotConnect: "Konnte keine Verbindung herstellen —",
    fillRequired: "Bitte füllen Sie alle erforderlichen Felder aus.",
    connectionFailed:
      "Verbindung fehlgeschlagen — überprüfen Sie Ihre Angaben und versuchen Sie es erneut.",
    reconnectionFailed:
      "Wiederherstellung der Verbindung fehlgeschlagen — die Datenbank ist möglicherweise nicht mehr verfügbar.",
    dbPlaceholderSqlite: "/Benutzer/sie/daten/mydb.db",
    dbPlaceholderDuckdb: "/Benutzer/sie/daten/mydb.duckdb",
    hostPlaceholder: "localhost oder db.firma.de",
    userPlaceholder: "ihr_benutzername",
    dbNamePlaceholder: "meine_datenbank",
    sqliteFileHint: "Der absolute Pfad zu Ihrer .db- oder .sqlite-Datei.",
    duckdbFileHint: "Der absolute Pfad zu Ihrer DuckDB-Datei.",
    dockerFileHint:
      "Bei Verwendung von Docker legen Sie die Datei im Datenordner des Projekts ab und verwenden /app/data/dateiname.db.",
    inMemoryDb: "Leer lassen, um eine In-Memory-Datenbank zu verwenden.",
    tablesCount: "{n} Tabelle{?n}",
    justNow: "gerade eben",
  },
  chat: {
    viewOnly: "schreibgeschützt",
    newConversation: "Neue Konversation",
    askPlaceholder: "Fragen Sie alles zu Ihren Daten\u2026",
    ariaAskQuestion: "Stellen Sie eine Frage zu Ihren Daten",
    askButton: "Fragen",
    scrollToLatest: "Zum Neuesten scrollen",
    tableCount: "{n} Tabelle{?n}",
    privacyFooter:
      "Nur das Schema und Ihre Frage werden an OpenRouter gesendet, um SQL zu generieren — niemals Ihre Zeilendaten.",
    sqlCommandDescription: "SQL-Abfrage direkt ausführen",
    directSql: "DIREKTES SQL",
    directSqlReason: "Direkte SQL-Ausführung",
    whatIUnderstood: "WAS ICH VERSTANDEN HABE",
    generatedSql: "Generiertes SQL",
    viewQuery: "Abfrage anzeigen",
    hideQuery: "Abfrage ausblenden",
    copy: "Kopieren",
    copied: "\u2713 Kopiert!",
    copyCsv: "\u2193 Als CSV kopieren",
    copiedCsv: "\u2713 Kopiert!",
    copyResponse: "Antwort kopieren",
    copyPrompt: "Prompt kopieren",
    editPrompt: "Prompt bearbeiten",
    regenerate: "Neu generieren",
    yesCorrect: "Ja, richtig",
    confirmationPrompt: "War das die gesuchte Antwort?",
    verifiedSaved: "Verifiziert — im Vertrauensverlauf gespeichert.",
    basedOnVerified: "Basierend auf einer zuvor verifizierten Antwort",
    highConfidence: "Hohe Zuversicht",
    mediumConfidence: "Mittlere Zuversicht",
    lowConfidence: "Niedrige Zuversicht",
    wrongNumbers: "Falsche Zahlen",
    wrongFilter: "Falscher Filter / Datumsangaben",
    wrongIntent: "Nicht das, was ich meinte",
    wrongMissing: "Fehlende Daten",
    wrongOther: "Etwas anderes",
    thoughtProcess: "Gedankengang",
    schemaLinked: "Schema verknüpft",
    validationPassed: "Validierung bestanden",
    validationFailed: "Validierung fehlgeschlagen",
    selfCorrection: "Selbstkorrektur",
    collapse: "Einklappen",
    conversations: "Konversationen",
    clearAll: "Alle löschen",
    noConversationsYet: "Noch keine Konversationen",
    deleteConversation: "Konversation löschen",
    emptyTitle: "Was möchten Sie wissen?",
    emptyDescription:
      "Stellen Sie eine beliebige Frage zu Ihren Daten in natürlicher Sprache. BoloDB wird sie beantworten und erklären, wie zuversichtlich es ist.",
    questionsVerifiedForDb: "Für diese Datenbank verifizierte Fragen:",
    clickAnyQuestion:
      "Klicken Sie auf eine Frage oben, um sie auszuführen, oder geben Sie unten Ihre eigene ein.",
    notSureWhereToStart: "Nicht sicher, wo Sie anfangen sollen? Versuchen Sie:",
    asYouVerify:
      "Wenn Sie Antworten verifizieren, werden hier Fragen spezifisch zu Ihren Daten angezeigt.",
    wantBetterAnswers: "Bessere Antworten gewünscht?",
    catalogDescription:
      'Erstellen Sie einen Datenkatalog mit Ihren Geschäftsbegriffen — fügen Sie sie manuell hinzu oder verwenden Sie "Mit KI vorschlagen" zum automatischen Ausfüllen.',
    powerUserHint:
      "Fortgeschrittener? Geben Sie /sql SELECT ... ein, um SQL direkt auszuführen.",
    executionFailed: "Ausführung fehlgeschlagen",
    sqlExecutionFailed: "SQL-Ausführung fehlgeschlagen",
    noMatchingCommands: "Keine passenden Befehle",
    noRowsMatched:
      "Keine Zeilen gefunden — es gibt möglicherweise keine Daten, die dieser Frage entsprechen.",
    rowsReturned: "{n} Zeile{?n} zurückgegeben",
    copySql: "SQL-Abfrage kopieren",
    copyCsvTitle:
      "Alle Zeilen als CSV kopieren — in Excel oder Sheets einfügen",
    chartView: "Diagramm",
    tableView: "Tabelle",
    conversationNotFound: "Konversation nicht gefunden",
    renamedSuccessfully: "Erfolgreich umbenannt",
    deletedSuccessfully: "Erfolgreich gelöscht",
    clearedSuccessfully: "Erfolgreich gelöscht",
    milestoneReached: "Genauigkeits-Meilenstein erreicht",
    milestoneAssistedBody:
      "Zuversichtliche Antworten werden jetzt sofort angezeigt — neue Fragen werden noch einmal überprüft.",
    fullyCalibrated: "Vollständig kalibriert",
    milestoneTrustedBody:
      "Alle Antworten erscheinen jetzt direkt. Der Gedankengang ist jederzeit einen Klick entfernt.",
    totalQueries: "Insgesamt: {n} Abfrage{?n}",
    accuracy: "Genauigkeit",
    verifiedCount: "{n} verifiziert",
    calibrateNext:
      "Verifizieren Sie {n} weitere richtige Antwort{?en}, um {goal} zu erreichen.",
    calibrateDirect:
      "zuversichtliche Antworten direkt anzeigen, ohne zu warten.",
    calibrateAll:
      "alle Fragen direkt beantworten — Gedankengang einen Klick entfernt.",
    calibrated: "BoloDB ist für diese Datenbank vollständig kalibriert.",
    schema: "Schema",
    turnCount: "{n} Durchgang{?\u00a4#Durchg\u00e4nge}",
    toggleSidebar: "Seitenleiste umschalten",
    expandThinking: "Gedankengang erweitern",
    collapseThinking: "Gedankengang einklappen",
    sqlAttempt: "SQL-Versuch {n}",
    passed: "Bestanden",
    beforeLabel: "VORHER",
    stepsCount: "{n} Schritt{?e}",
    repairsCount: "{n} Reparatur{?en}",
    rowsCount: "{n} Zeile{?n}",
    resultsTruncated: "Ergebnisse gekürzt — erste {n} Zeilen angezeigt",
    thanksWhatsOff: "Danke — was war falsch?",
    mostUsefulSignal: "(dies ist das nützlichste Signal)",
    tellingUsKeepsAccurate:
      "Ihr Feedback hält BoloDB genau — verifizierte Antworten werden zu Beispielen für zukünftige Fragen.",
    loggedAs: 'Als "{reason}" protokolliert.',
    executionErrorTitle: "Die Abfrage hatte ein Problem",
    executionErrorDesc:
      "BoloDB hat eine Abfrage generiert, aber Ihre Datenbank konnte sie nicht ausführen — dies passiert manchmal, wenn ein Spalten- oder Tabellenname nicht richtig zugeordnet wurde.",
    executionErrorHint:
      "Versuchen Sie, Ihre Frage umzuformulieren, eine bestimmte Tabelle oder Metrik zu nennen oder fragen Sie mit mehr Kontext erneut.",
    ifResultLooksRight:
      'Wenn das Ergebnis richtig aussieht, klicken Sie unten auf "Ja, richtig" — das trainiert BoloDB für das nächste Mal.',
    trusted: "Vertrauenswürdig",
    assisted: "Unterstützt",
    supervised: "Überwacht",
    trustedBehaviour:
      "Antworten werden direkt angezeigt. Gedankengang ist einen Klick entfernt.",
    assistedBehaviour:
      "Zuversichtliche Antworten werden angezeigt; neue werden noch einmal überprüft.",
    supervisedBehaviour:
      "Jede Antwort wartet auf Ihre Bestätigung, während die KI lernt.",
    providerOpenRouterName: "OpenRouter",
    providerOpenRouterSub: "OpenRouter-API",
    providerOpenRouterPrivacy:
      "Schema + Frage an Google gesendet — niemals Ihre Zeilendaten",
    providerOpenRouterCost:
      "Kostenloses Kontingent verfügbar, dann nutzungsabhängige Bezahlung",
    providerOpenRouterAccuracy: "Höchste",
    providerDefault: "Standard",
  },
  settings: {
    title: "Einstellungen",
    close: "Einstellungen schließen",
    googleOpenRouter: "OpenRouter",
    powersAi: "Betreibt jede KI-Funktion in BoloDB",
    model: "Modell",
    modelDefaultHint:
      'Nicht sicher? Bleiben Sie bei "Ausgewogen" — es funktioniert gut für die meisten Datenbanken.',
    modelFast: "Schnellste & günstigste — gut für kleine, einfache Datenbanken",
    modelBalanced:
      "Ausgewogen — für die meisten Anwendungen empfohlen (Standard)",
    modelAccurate: "Genaueste — für große Schemata und schwierige Fragen",
    apiKey: "OpenRouter-API-Schlüssel",
    keyConfigured: "API-Schlüssel konfiguriert",
    cancelKeepKey: "\u2190 Abbrechen, vorhandenen Schlüssel behalten",
    getKeyAt: "Kostenlosen Schlüssel erhalten unter",
    keyStoredLocally:
      "Nur lokal gespeichert. Schema + Frage werden an OpenRouter gesendet, um SQL zu generieren — niemals Ihre Tabellendaten.",
    dataCatalog: "Datenkatalog",
    catalogDescription:
      "Bringen Sie BoloDB Ihre Geschäftsbegriffe, Metriken und Wertbedeutungen bei, damit Antworten genauer werden.",
    manageCatalog: "Datenkatalog verwalten \u2192",
    changeDbPrompt: "Möchten Sie eine andere Datenbank verbinden?",
    disconnectButton: "Trennen & Datenbank wechseln",
    couldNotSave: "Einstellungen konnten nicht gespeichert werden.",
    couldNotRemoveKey: "Schlüssel konnte nicht entfernt werden.",
    language: "Sprache",
  },
  dashboard: {
    title: "Dashboard",
    connection: "Verbindung",
    database: "Datenbank",
    status: "Status",
    model: "Modell",
    confidenceDistribution: "Vertrauensverteilung",
    queryActivity: "Abfrageaktivität",
    backToChat: "Zurück zum Chat",
    noQueriesYet: "Noch keine Abfragen",
    noActivityYet: "Noch keine Aktivität",
    noChartableFormat: "Diese Daten haben kein diagrammfähiges Format.",
    noTableUsage: "Keine Tabellennutzungsdaten",
    noSchemaData: "Keine Schemadaten",
  },
  onboard: {
    title: "Onboarding — BoloDB",
    dbLabel: "Datenbank",
    tableLabel: "Tabelle",
    aiError:
      "Die KI antwortet nicht — überprüfen Sie Ihren API-Schlüssel in den Einstellungen.",
    settingsTip: "Sie können diese Einstellungen später ändern.",
    autoRun: "automatisch ausführen",
    viewSql: "Technische Details anzeigen (SQL)",
    notQuite: "Nicht ganz",
    yesThatsRight: "Ja, das stimmt",
    gettingToKnowDb: "Ihre Datenbank kennenlernen",
    profileDescription:
      "Lassen Sie mich Ihre Tabellen und Spalten ansehen, damit ich Fragen genau beantworten kann.",
    linked: "verknüpft",
    readingDb: "Lesen Ihrer Datenbank\u2026",
    looksGoodContinue: "Sieht gut aus — weiter",
    confirmTerms: "Bestätigen Sie, was Ihre Begriffe bedeuten",
    glossaryDescription:
      "Ich habe Begriffe in Ihrem Schema gefunden, die speziell sein könnten. Sagen Sie mir, was sie bedeuten, damit ich richtig antworte.",
    means: "bedeutet\u2026",
    suggested: "VORGESCHLAGEN",
    saveTermsAndVerify: "Begriffe speichern & Antworten verifizieren",
    checkAnswersBeforeStart:
      "Überprüfen Sie einige Antworten, bevor Sie beginnen",
    startersDescription:
      "Lassen Sie mich einige automatisch generierte Abfragen ausführen, damit Sie zuerst überprüfen können, ob sie richtig sind.",
    statusCorrect: "Richtig! Im Vertrauensverlauf gespeichert.",
    statusWrong: "Als falsch markiert — ich werde daraus lernen.",
    statusSkipped: "Sie können später jederzeit im Chat verifizieren.",
    startersError:
      "Beispielabfragen konnten nicht generiert werden — Sie können diesen Schritt überspringen.",
    startAsking: "Fragen stellen \u2192",
    reviewEachAnswer: "Überprüfen Sie jede Antwort oben, um fortzufahren.",
    stepReadDb: "DB lesen",
    stepDefineTerms: "Begriffe definieren",
    stepCheckAnswers: "Antworten überprüfen",
    doesResultLookCorrect: "Sieht die Ergebnistabelle richtig aus?",
    savedReference: "Gespeichert — dies wird eine Referenzantwort",
    skippedNoted: "Übersprungen — zur Kenntnis genommen, wird nicht verwendet",
  },
  schema: {
    title: "Schema",
    trustSupervised:
      "Jede Antwort wartet auf Ihre Bestätigung, während die KI lernt.",
    trustAssisted:
      "Zuversichtliche Antworten werden angezeigt; neue werden noch einmal überprüft.",
    trustTrusted:
      "Antworten werden direkt angezeigt. Gedankengang ist einen Klick entfernt.",
    supervised: "Überwacht",
    assisted: "Unterstützt",
    trusted: "Vertrauenswürdig",
    synonyms: "Synonyme",
    valueMeanings: "Wertbedeutungen",
    metrics: "Metriken",
    joinPaths: "Join-Pfade",
    columnNotes: "Spaltennotizen",
    suggestWithAi: "Mit KI vorschlagen",
    saveCatalog: "Katalog speichern",
    cancel: "Abbrechen",
    close: "Datenkatalog schließen",
    removeRow: "Zeile entfernen",
    loading: "Katalog wird geladen\u2026",
    couldNotLoad: "Katalog konnte nicht geladen werden.",
    suggestionsLoaded:
      "KI-Vorschläge geladen — überprüfen und bearbeiten, dann speichern.",
    couldNotSuggest: "Vorschläge konnten nicht generiert werden.",
    couldNotSave: "Katalog konnte nicht gespeichert werden.",
    catalogPageDescription:
      "Bringen Sie BoloDB Ihre Geschäftssprache bei. Sie wird mit jeder Frage gesendet, um genauer zu antworten.",
    synonymsDesc:
      "Geschäftswörter, die Ihr Team verwendet, einer Tabelle oder Spalte zugeordnet.",
    valueMeaningsDesc:
      'Ein benutzerfreundliches Label für einen gespeicherten Wert, z. B. "VIP" bedeutet segment = vip.',
    metricsDesc:
      "Wiederverwendbare Berechnungen, z. B. umsatz = SUM(gesamtbetrag) WHERE abgeschlossen.",
    joinPathsDesc:
      "Wie Tabellen verbunden sind, damit Antworten sie richtig verknüpfen.",
    columnNotesDesc:
      "Was eine Spalte bedeutet, wenn der Name allein nicht klar ist.",
    thinking: "Denke\u2026",
    saving: "Speichern\u2026",
    entry: "{n} Eintrag{?\u00a4#Eintr\u00e4ge}",
  },
  errors: {
    dbConnectionRefused:
      "Der Datenbankserver läuft nicht oder ist nicht erreichbar — überprüfen Sie Host und Port.",
    wrongCredentials:
      "Falscher Benutzername oder falsches Passwort — überprüfen Sie Ihre Anmeldedaten.",
    fileNotFound:
      "Datei nicht gefunden — überprüfen Sie den Pfad und stellen Sie sicher, dass die Datei existiert.",
    dbDoesNotExist:
      "Dieser Datenbankname wurde nicht gefunden — überprüfen Sie die Schreibweise.",
    connectionTimedOut:
      "Verbindung zeitüberschreitung — der Server ist möglicherweise nicht erreichbar oder befindet sich hinter einer Firewall.",
    sslError:
      "SSL-Fehler — bei Verbindung über URL-Modus versuchen Sie, ?sslmode=disable am Ende hinzuzufügen.",
    driverNotInstalled:
      "Der Treiber für diesen Datenbanktyp ist auf diesem Server nicht installiert.",
    accessDenied: "Zugriff verweigert",
    sessionExpired: "Sitzung abgelaufen, bitte erneut anmelden",
    invalidToken: "Ungültiges Token",
    invalidCredentials: "Ungültige Anmeldedaten",
    emailAlreadyRegistered: "E-Mail bereits registriert",
    invalidGoogleToken: "Ungültiges Google-Token",
    googleNoEmail: "Google-Konto hat keine E-Mail",
    googleEmailNotVerified: "Google-E-Mail ist nicht verifiziert",
    userNotFound: "Benutzer nicht gefunden",
    incorrectPassword: "Falsches Passwort, bitte versuchen Sie es erneut",
    internalError: "Ein interner Fehler ist aufgetreten.",
    noDatabaseConnected: "Keine Datenbank verbunden",
    emptyQuestion: "Leere Frage",
    couldNotFormQuery:
      "Konnte keine Abfrage erstellen — versuchen Sie es umzuformulieren",
    couldNotFormWorkingQuery:
      "Konnte keine funktionierende Abfrage erstellen — versuchen Sie es umzuformulieren",
    sqlGenerationTimeout:
      "SQL-Generierung hat das maximale Zeitlimit überschritten",
    queryGenerationFailed: "Abfragegenerierung fehlgeschlagen",
    modelReturnedEmptySql: "Modell hat leeres SQL zurückgegeben",
    retryingCorrections: "Wiederhole mit Korrekturen",
    queryCouldNotRun:
      "Die Abfrage konnte nicht gegen die Datenbank ausgeführt werden.",
    couldNotGenerateValidSql:
      "Konnte nach {n} Versuchen kein gültiges SQL generieren",
    noDatabaseConnectedShort: "Keine Datenbank verbunden",
    emptyStatement: "Leere Anweisung.",
    selectOnly: "Nur SELECT-Abfragen sind erlaubt (schreibgeschützter Modus).",
    singleStatementOnly:
      "Nur eine Anweisung ist erlaubt (keine gestapelten Abfragen).",
    selectIntoNotAllowed: "SELECT INTO ist nicht erlaubt.",
    aiKeyInvalid:
      "Der KI-API-Schlüssel scheint ungültig oder abgelaufen zu sein.",
    aiKeyDenied:
      "Der KI-Dienst hat den Zugriff verweigert — überprüfen Sie Ihren API-Schlüssel.",
    aiModelNotFound: "Das angeforderte KI-Modell wurde nicht gefunden.",
    aiUnexpectedError:
      "Der KI-Dienst hat einen unerwarteten Fehler zurückgegeben.",
    aiDeclined: "Die KI hat die Beantwortung dieser Frage abgelehnt.",
    aiEmptyAnswer:
      "Die KI hat eine leere Antwort zurückgegeben — bitte versuchen Sie es erneut.",
    llmError: "LLM-Fehler: {error}",
    entryNotFound: "Eintrag nicht gefunden oder nicht autorisiert",
    reasonQueryDidNotRun: "die generierte Abfrage wurde nicht ausgeführt",
    reasonMatchesVerified:
      "stimmt weitgehend mit einer zuvor verifizierten Antwort überein",
    reasonSimilarToVerified: "ähnlich einer zuvor verifizierten Antwort",
    reasonNoMatchingRows: "keine passenden Zeilen",
    reasonNewQuestion:
      "neue Frage — bitte bestätigen Sie, dass sie richtig ist",
  },
  streaming: {
    scanningTables: "Durchsuche Tabellen: {tables}",
    translatingTerm: "Übersetze Geschäftsbegriff: '{term}'",
    generatingSql: "Generiere SQL\u2026",
    runningQuery: "Führe Abfrage aus\u2026",
    validating: "Validiere\u2026",
  },
  chart: {
    chart: "Diagramm",
    table: "Tabelle",
  },
} satisfies BaseTranslation;

export default de;
