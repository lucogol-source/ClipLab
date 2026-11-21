# ClipLab V2.1.1 per Mac e Windows

Per l’installazione guidata e l’uso quotidiano, apri **README.txt**, incluso nei pacchetti Mac e Windows. Su Windows x64 usa **Avvia ClipLab.cmd**: prepara Python, Node.js e gli altri componenti nella cartella dell’app. I file `.command` descritti nella sezione seguente sono per Mac. La nuova edizione Windows richiede ancora una verifica nativa su PC; i test automatici sono eseguiti sul Mac di sviluppo.

Un’app locale per trasformare un video YouTube o un file in clip e caricarle sul proprio canale. Non richiede abbonamenti, crediti AI, chiavi API a pagamento o servizi di trascrizione esterni.

## Avvio su Mac

Fai doppio clic su **Avvia ClipLab.command**. Si apre l’indirizzo locale mostrato dal launcher: riutilizza il motore della stessa installazione oppure sceglie una porta libera tra `8765` e `8768–8778`. Due copie in cartelle distinte possono funzionare insieme; non possono condividere la stessa cartella dati mentre sono attive. La versione è visibile nella barra superiore dell’app. Il motore continua a funzionare anche se chiudi il Terminale o la chat; il Mac deve restare acceso durante il lavoro. Per arrestare il motore fai doppio clic su **Ferma ClipLab.command**. Dopo un riavvio del Mac, avvia nuovamente ClipLab.

Sul Mac dove è stata creata l’app i componenti, Whisper Base, Whisper Small e il modello volti sono già installati. Il pacchetto ZIP contiene il codice e non i modelli o i tuoi progetti. Su un altro Mac, il launcher scarica automaticamente Python 3.12 e i componenti gratuiti nella cartella dell’app. Per preparare Small prima dell’uso esegui **Aggiorna ClipLab.command** dopo il primo avvio. Sono necessari connessione e spazio su disco; gli strumenti non hanno un canone. Se sposti la cartella e Python non parte, elimina soltanto `.venv` e riavvia il launcher: verrà ricreata.

## Flusso

1. Incolla un singolo link YouTube oppure scegli un file locale (max 2 GB / 2 ore).
2. Scegli formato, durata indicativa, numero di proposte e stile dei sottotitoli.
3. Whisper trascrive audio e tempi delle parole sul Mac. Il selettore locale propone passaggi in base a apertura, densità del parlato e fine frase. Può produrre meno clip di quelle richieste se il video non contiene abbastanza passaggi distinti.
4. Apri una proposta e modifica taglio, titolo, inquadratura e sottotitoli. L’anteprima mostra il movimento e la traccia del testo; controlla il risultato definitivo nell’MP4 esportato.
5. Esporta l’MP4 e il file SRT. Con gli account collegati puoi caricare su YouTube oppure programmare le clip a intervalli per le piattaforme disponibili.

Le uscite sono H.264/AAC. A 1080p: **1080×1920** in 9:16, **1080×1080** in 1:1, **1920×1080** in 16:9. Puoi scegliere anche 720p per un rendering più rapido. Ogni clip dura al massimo 180 secondi. L’editor include ritaglio, immagine intera con bande/sfondo sfocato, doppio riquadro podcast, zoom/pan manuale e tracking visivo dei volti. Puoi scegliere un volto e modificare i punti del movimento. Il tracking non identifica automaticamente il parlante dall’audio. Non c’è un modello linguistico remoto né una previsione della viralità. La precisione della trascrizione dipende dall’audio e dal modello; controlla nomi, numeri e sottotitoli prima della pubblicazione.

## Collegare il canale YouTube (gratuito)

L’app non contiene credenziali Google preconfezionate. L’account Google deve autorizzare un progetto personale tramite OAuth:

1. Crea un progetto in [Google Cloud Console](https://console.cloud.google.com/projectcreate).
2. In **API e servizi → Libreria**, abilita **YouTube Data API v3**.
3. In **Google Auth Platform**, configura nome e pubblico dell’app. Se usi la modalità test, aggiungi la tua email come utente di test.
4. Crea un **ID client OAuth** di tipo **App desktop** e scarica il JSON. Non usare una semplice API key o un service account.
5. In ClipLab apri **Canali social**, carica il JSON nella sezione YouTube e premi **Collega il canale**.
6. Completa personalmente l’accesso e il consenso Google. Seleziona l’account/canale corretto, incluso l’eventuale Brand Account. Il nome e l’ID effettivi del canale saranno mostrati nell’app.

Servono gli scope `youtube.upload` e `youtube.readonly`: uno carica i video, l’altro verifica il canale di destinazione. Con un progetto OAuth in test i token possono scadere dopo 7 giorni: in quel caso ricollega il canale. ClipLab non ha accesso alla password Google.

La quota API e gli eventuali limiti giornalieri di caricamento sono gestiti da Google. ClipLab non attiva fatturazione, non acquista quote e non aggira i limiti. Se la quota o l’autorizzazione non consentono l’upload, mantiene gli MP4 sul Mac e mostra l’errore.

Documentazione ufficiale: [YouTube videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert), [quote API](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits), [OAuth desktop](https://developers.google.com/identity/protocols/oauth2/native-app).

## Flusso completamente automatico

Dopo aver collegato YouTube, nello Studio attiva **Esporta e carica automaticamente su YouTube**. Scegli visibilità e indicazione relativa ai bambini. Prima di avviare il lavoro l’app mostra canale e visibilità. Il processo scarica/importa, trascrive, seleziona, esporta e carica tutte le clip proposte con le impostazioni scelte, senza attendere una revisione editoriale. Per rifinire prima le proposte lascia disattivata questa opzione.

La visibilità predefinita è **Privato**. Scegli **Pubblico** per pubblicare direttamente sul canale. Una clip già caricata non viene ricaricata automaticamente. In caso di esito incerto dopo un problema di rete, l’app blocca un nuovo tentativo per evitare duplicati: verifica YouTube Studio. Se necessario crea un nuovo progetto soltanto dopo aver escluso la presenza del video.

Non ricerca autonomamente i video virali: importa i link che inserisci. La programmazione riguarda gli MP4 già esportati, non l’importazione futura di nuove sorgenti. Usa contenuti tuoi o per cui hai i diritti di riutilizzo. Il ritaglio e l’aggiunta di sottotitoli non concedono diritti su video di altri creator.

## Dati e riservatezza

- Video, trascrizioni, esportazioni e progetti: `.data/projects/`.
- Modelli vocali: `.data/models/` (Base circa 145 MB, Tiny circa 75 MB, Small circa 465 MB; oltre alle librerie).
- JSON OAuth e token: `.data/secrets/`, con accesso ai file limitato all’utente locale. Non condividere questa cartella o l’installazione completa con i token dentro.
- **Scollega dal Mac** dimentica il token locale. Per revocare anche il consenso usa [le connessioni Google](https://myaccount.google.com/permissions).
- Il server ascolta solo su `127.0.0.1` e rifiuta richieste di modifica provenienti da altri siti.
- Eliminare un progetto rimuove i relativi file dal Mac; non elimina i video già caricati su YouTube.

Non ci sono telemetria, pubblicità o analisi del contenuto esterne. L’app contatta YouTube per download/upload, Google e TikTok per le integrazioni configurate, Hugging Face e OpenCV Zoo per i modelli gratuiti. Durante l’installazione contatta anche i registri ufficiali dei componenti.

## Se qualcosa non funziona

- **Motore scollegato / importazione fallita:** apri **Avvia ClipLab.command**, poi premi **Riprova connessione** nella pagina. L’app controlla la connessione e conserva il link inserito. I dettagli di avvio sono in `.data/server.log`.
- **Download YouTube bloccato:** alcuni video non sono disponibili o YouTube può richiedere un controllo aggiuntivo. L’app non legge i cookie del browser e non aggira blocchi. Usa il file originale nella scheda File locale.
- **Nessun parlato:** viene proposta una clip iniziale modificabile, senza sottotitoli.
- **Trascrizione lenta:** prova Tiny, riduci la durata della sorgente o usa Base invece di Small. L’inferenza usa la CPU del Mac.
- **Upload rifiutato:** controlla API abilitata, utente di test, canale e quota; poi ricollega Google se necessario.
- **Interruzione o riavvio:** i risultati completati restano; i lavori interrotti sono segnalati e non vengono ripresi automaticamente.

## Sviluppo e verifiche

Backend Python/FastAPI, PyAV, faster-whisper, yt-dlp, FFmpeg tramite imageio-ffmpeg, OpenCV YuNet e client Google ufficiali. Il rendering OpenCV viene eseguito in un processo separato per evitare conflitti fra librerie video su macOS. Interfaccia HTML/CSS/JavaScript senza build e senza CDN. Le versioni installate sono in `requirements.lock.txt`.

La versione dell’app è definita una sola volta in `version.py`, condivisa da backend e frontend. Le novità e i controlli eseguiti sono elencati in [CHANGELOG.md](CHANGELOG.md). Il backup del codice precedente è in `../backup/ClipLab-V2.1.0`; non contiene i progetti o le credenziali personali.

Avvio manuale: `.venv/bin/python server.py`. Test locali: `.venv/bin/python -m unittest discover -s tests -v`. Il test end-to-end opzionale è descritto in `tests/verify_pipeline.py`. Nessun test pubblica video reali su YouTube.

L’app è sviluppata per uso personale e non è affiliata ai servizi confrontati. La pubblicazione reale richiede i tuoi account e le autorizzazioni delle piattaforme; finora è stata verificata tramite test simulati, senza invii reali.

## Novità: sottotitoli, editor e programmazione

Leggi [CONFRONTO-E-NOVITA.md](CONFRONTO-E-NOVITA.md) per il confronto con OpusClip, Vizard, quso.ai, 2short.ai, NoonFrame e WayinVideo, e i limiti precisi delle funzioni.

- Nell’editor scegli **Sottotitoli** per correggere testo e tempi, cambiare colore/dimensione/margini o ritrascrivere soltanto la clip con Whisper Small e un glossario.
- Per preparare Whisper Small e il modello volti, esegui **Aggiorna ClipLab.command** una volta. I download sono gratuiti. Small richiede circa 465 MB; una connessione lenta può richiedere diversi minuti. La ripresa del download conserva i dati ricevuti.
- In **Inquadratura** puoi trascinare il video, regolare zoom e pan, usare i layout intero, sfocato e podcast doppio, oppure generare il tracking volti. **Aggiungi punto qui** salva l’inquadratura nella posizione corrente della timeline.
- **Salva modifiche** conserva il progetto sul Mac. **Esporta MP4 senza watermark** genera una nuova versione e un SRT. Non viene aggiunto alcun watermark; i loghi presenti nella sorgente non vengono cancellati.
- Dopo aver esportato, scegli **Programma le clip**, seleziona gli MP4 e le piattaforme, imposta prima data e intervallo e conferma la revisione dei contenuti. La pagina **Pubblicazioni** mostra la coda, consente pausa e annullamento.
- La coda è locale: il Mac deve restare acceso con ClipLab attivo. Non avvia una macchina cloud né richiede un servizio di scheduler a pagamento.
- In **Canali social** puoi configurare YouTube e TikTok separatamente. TikTok richiede credenziali Desktop e accesso Content Posting API: il test è privato; l’accesso pubblico richiede l’approvazione della piattaforma, non garantita per strumenti personali o di ripubblicazione.
- Le funzioni di pubblicazione reale si possono verificare soltanto dopo il collegamento dei tuoi account. Nessun test incluso pubblica video reali.
