CLIPLAB V2.4.0 — INSTALLAZIONE E UTILIZZO
Windows x64 e macOS — guida da condividere insieme al programma

COME AVVIARE CLIPLAB — IL FILE DA APRIRE CON DOPPIO CLIC

Estrai lo ZIP del tuo sistema operativo e apri la cartella ClipLab estratta.

  Mac             Nel Finder fai doppio clic su “Avvia ClipLab.command”.
  Windows 10/11   In Esplora file fai doppio clic su “Avvia ClipLab.cmd”.

Se le estensioni dei file sono nascoste, vedrai il nome “Avvia ClipLab”.
Al primo avvio tieni il computer connesso a Internet e attendi che finisca
la configurazione. ClipLab apre lo Studio nel browser. Se la scheda non si
apre, usa l’indirizzo locale indicato nella finestra di avvio.
Per riaprire lo Studio, anche dopo aver riavviato il computer, fai di nuovo
doppio clic sullo stesso file “Avvia ClipLab”.

COS’È
ClipLab crea brevi clip da un video YouTube o da un file locale. Include
trascrizione sul computer, sottotitoli modificabili, editor di inquadratura,
zoom/tracking dei volti, esportazione MP4/SRT e coda di pubblicazione social.
Non richiede Codex, ChatGPT, abbonamenti o chiavi AI a pagamento.
Trascrizione e rendering usano la CPU del computer.

1. QUALE PACCHETTO USARE

- Windows: ClipLab-V2.4.0-Windows.zip, destinato a Windows 10/11 x64 su
  processori Intel o AMD. Non include una build nativa ARM o Windows 32 bit.
- Mac: ClipLab-V2.4.0-Mac.zip. I comandi da usare hanno estensione .command.

Inviare lo ZIP preparato, non la propria cartella di lavoro completa.
I pacchetti escludono video, progetti, account, token e componenti installati.
Ogni destinatario configura sul proprio computer i propri account social.

2. INSTALLAZIONE SU WINDOWS

1) Salva lo ZIP sul PC. Clic destro sul file > Estrai tutto.
   Apri la cartella estratta ClipLab. Non avviare i file dentro lo ZIP.
   Usa una cartella locale stabile e scrivibile, per esempio Documenti\ClipLab.

2) Sono necessari Internet per la prima installazione, spazio per componenti,
   modelli e video e un browser. Non serve una scheda grafica NVIDIA.
   Le librerie Windows richiedono Microsoft Visual C++ Redistributable x64.
   Se manca o compare “DLL load failed”, installa il componente gratuito
   ufficiale e riprova:
   https://aka.ms/vc14/vc_redist.x64.exe
   Documentazione Microsoft:
   https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist

3) Fai doppio clic su “Avvia ClipLab.cmd”.
   L’installazione prepara nella cartella dell’app Python 3.12, le librerie,
   FFmpeg, Node.js per i link YouTube e il modello dei volti. Non occorre
   installare Python o Node.js separatamente o modificare il PATH di Windows.
   Il download di Node.js è verificato con il checksum ufficiale del progetto.
   Alla prima esecuzione attendi che i download e l’installazione finiscano.

4) Si apre il browser all’indirizzo locale indicato nella finestra, normalmente
   http://127.0.0.1:8765/ oppure una porta libera tra 8768 e 8778.
   Se il browser non si apre, copia l’indirizzo mostrato nella finestra.
   La versione effettiva del motore compare nella barra superiore dell’app.

5) Esegui una volta “Aggiorna ClipLab.cmd” per preparare anche Whisper Small,
   il modello consigliato per i sottotitoli. Occupa circa 465 MB, oltre alle
   librerie. Il modello si scarica una volta e viene poi riutilizzato.
   I download interrotti possono essere ripresi rieseguendo il comando.
   Questo comando prepara i modelli: non scarica nuove versioni dell’app.

COMANDI WINDOWS
Avvia ClipLab.cmd        Installa ciò che manca e avvia l’app.
Aggiorna ClipLab.cmd     Prepara i modelli locali, incluso Whisper Small.
Ferma ClipLab.cmd        Richiede l’arresto del motore di questa installazione.
Diagnostica ClipLab.cmd  Controlla componenti, FFmpeg e Node.js senza mostrare
                        credenziali o leggere i contenuti dei tuoi progetti.
Configura ClipLab.cmd   Componente richiamato automaticamente dall’avvio.

Non eseguire i file .command su Windows. Non spostare la cartella dopo aver
installato i componenti: i percorsi di Python possono dipendere dalla posizione.

3. INSTALLAZIONE SU MAC

1) Estrai ClipLab-V2.4.0-Mac.zip in una cartella locale stabile e scrivibile.
2) Fai doppio clic su “Avvia ClipLab.command” e attendi la prima configurazione.
3) Esegui “Aggiorna ClipLab.command” una volta per preparare Whisper Small.
4) Per arrestare il motore usa “Ferma ClipLab.command”.

Per i link YouTube serve un runtime JavaScript supportato. Il launcher Mac
non installa Node.js automaticamente: se non è presente, installa gratuitamente
Node.js LTS per Mac, versione 22 o successiva, dal sito ufficiale:
https://nodejs.org/en/download/
L’importazione da File locale non richiede Node.js.

4. PRIMA PROVA CONSIGLIATA

1) Apri lo Studio e scegli “File locale”.
2) Seleziona un video breve con parlato, tuo o che puoi riutilizzare.
3) Imposta una sola clip e il formato 9:16; avvia l’elaborazione.
4) Aspetta che il progetto sia pronto, quindi apri una clip nell’editor.
5) Esporta e guarda l’intero MP4 prima di passare a video lunghi.

In alternativa usa la scheda “Link YouTube” e incolla il link di un singolo
video. Sono supportate sorgenti fino a 2 ore / 2 GB; non playlist o live in corso.
Alcuni video possono essere indisponibili o richiedere controlli di YouTube.

DIVIDERE L’INTERO VIDEO

Nel modulo iniziale scegli “Dividi tutto il video” in “Come creare le clip”.
Imposta la durata di ogni parte (30, 45, 60, 90, 120 o 180 secondi).
ClipLab copre il video da inizio a fine, includendo pause e tratti senza parlato.
Un video di 30 minuti con parti da 60 secondi produce 30 clip, in ordine.
L’ultima clip contiene il tempo rimanente. Se il resto è inferiore a mezzo
secondo, il confine precedente arretra per ottenere un’ultima clip di 0,5 s.
Ogni clip può essere adattata nell’editor ed esportata. Le proposte di taglio
si salvano nel progetto; l’MP4 viene creato quando esporti la singola clip.
Se attivi “Esporta e carica automaticamente su YouTube”, autorizzi l’esportazione
e il caricamento di tutte le parti. Tempi, spazio e quota YouTube crescono con
il numero di clip. Per la coda programmata puoi selezionare fino a 40 clip
per gruppo. I limiti della sorgente restano 2 ore e 2 GB.

TITOLI, HASHTAG E DOWNLOAD MULTIPLO

Le nuove clip ricevono un titolo dal tono enfatico basato sul testo e sul
titolo della sorgente. La generazione usa regole locali gratuite. Puoi
correggerlo nell’editor oppure premere “Genera titolo forte” per una proposta.
Nell’editor trovi anche “Descrizione e hashtag” e “Aggiorna hashtag”.

Alla creazione ClipLab consulta il feed pubblico Google Trends Italia per
i temi cercati nelle ultime 24 ore. Gli hashtag legati alle tendenze vengono
aggiunti quando i loro termini sono presenti nel contesto della clip.
Nell’editor puoi vedere fonte, ora del controllo e hashtag pertinenti trovati.
La cache dura 10 minuti. Se manca la connessione o il feed non risponde, vengono
usati i termini del contenuto e viene indicata l’indisponibilità delle tendenze.
Google Trends misura le ricerche Google; questi dati suggeriscono temi attuali.
Le descrizioni YouTube e le didascalie TikTok ricevono gli hashtag della clip.
La generazione di titoli e hashtag non garantisce visualizzazioni.

Per scaricare più video, prima esporta le clip desiderate. Seleziona le
caselle delle clip o “Seleziona le clip esportate”, poi “Scarica selezionati”.
Lo ZIP contiene gli MP4, gli SRT disponibili e un file TXT e JSON per ogni
clip con titolo, descrizione, hashtag e informazioni sulla fonte delle tendenze.
Le clip modificate richiedono una nuova esportazione. Lo ZIP viene preparato
temporaneamente sul disco: serve spazio libero per copiarvi le clip selezionate.

5. EDITOR, INQUADRATURA E SOTTOTITOLI

- Modifica titolo, inizio e fine della clip. I tempi sono nel formato min:sec.
- In “Inquadratura” scegli 9:16, 1:1 o 16:9. Usa ritaglio, immagine intera,
  sfondo sfocato o due riquadri per podcast. Trascina l’immagine o regola zoom
  e posizione. Puoi aggiungere punti per far cambiare inquadratura nel tempo.
- “Rileva volti e adatta” genera il tracking del volto selezionato. Segue
  visivamente un volto; non riconosce dall’audio chi sta parlando.
- In “Sottotitoli” correggi testo e tempi, regola dimensione, colore e posizione.
  Puoi ritrascrivere soltanto la clip con Small e suggerire nomi nel glossario.
  Controlla comunque nomi, numeri e punteggiatura: la trascrizione può sbagliare.
- “Salva modifiche” conserva il progetto. Dopo una modifica riesporta l’MP4.
- “Esporta MP4 senza watermark” crea il file finale a 1080p o 720p.
  “Scarica MP4” e “SRT” salvano i risultati tramite il browser.

Ogni clip dura al massimo 180 secondi. ClipLab non aggiunge watermark;
eventuali loghi già presenti nella sorgente restano visibili.
La selezione automatica propone passaggi sul parlato: non garantisce viralità.

6. COLLEGARE YOUTUBE E TIKTOK

Per montare ed esportare non occorre collegare alcun account.
Per pubblicare apri “Canali social” e usa soltanto i tuoi account.

YouTube: crea un progetto personale Google, abilita YouTube Data API v3,
configura il consenso OAuth, crea credenziali di tipo “App desktop”, scarica
il JSON e caricalo nell’app. Poi autorizza il canale corretto con il tuo account.
La procedura completa e i link ufficiali sono nel file LEGGIMI.md.
I token Google in modalità test possono richiedere un nuovo collegamento.

TikTok: servono credenziali Desktop e permessi Content Posting API appropriati.
Senza approvazione della piattaforma gli invii sono limitati al privato;
l’approvazione per strumenti personali di ripubblicazione non è garantita.
Se il collegamento non è disponibile puoi comunque esportare l’MP4 e caricarlo
manualmente dal tuo account. Dettagli e fonti: LEGGIMI.md / CONFRONTO-E-NOVITA.md.

ClipLab non attiva fatturazione e non acquista quote. Le piattaforme applicano
i propri limiti e possono rifiutare un invio. Usa contenuti che puoi pubblicare.

7. PROGRAMMARE LE PUBBLICAZIONI

Esporta e rivedi le clip. Scegli “Programma le clip”, seleziona gli MP4,
la piattaforma, la visibilità, la prima data e l’intervallo tra gli invii.
Conferma la pubblicazione. La pagina “Pubblicazioni” mostra la coda e permette
di metterla in pausa o annullare lavori ancora in attesa.

Il computer deve restare acceso, connesso a Internet e con ClipLab attivo.
La sospensione interrompe l’esecuzione puntuale. Il motore può continuare
anche chiudendo la scheda del browser o la finestra di avvio.
Dopo un riavvio del computer devi riaprire Avvia ClipLab.
Modificare una clip già programmata richiede una nuova esportazione e revisione.
Un invio dall’esito incerto non viene ripetuto automaticamente: controlla prima
il tuo account social per evitare duplicati.

8. DOVE SONO SALVATI I DATI

.data/projects/  Video, trascrizioni, progetti ed esportazioni.
.data/models/    Modelli vocali e rilevamento volti.
.data/secrets/   Credenziali e token dei tuoi account: non condividere.
.data/server.log Dettagli utili se il motore non parte.
.venv/ .runtime/ .tools/ .cache/  Componenti preparati su quel computer.

Su Mac queste cartelle possono essere nascoste nel Finder.
Le cartelle di componenti non vanno trasferite da Mac a Windows o viceversa.
Per passare l’app a un’altra persona usa sempre lo ZIP di distribuzione pulito.
La cancellazione della cartella dell’app elimina anche i dati contenuti al suo
interno: conserva copie dei video e progetti che vuoi mantenere.

9. SE QUALCOSA NON FUNZIONA

- “Motore scollegato”: riapri Avvia ClipLab e poi “Riprova connessione”.
- “Versione precedente”: riapri Avvia ClipLab nella cartella corrente.
  Il launcher apre il browser sull’indirizzo corretto; puoi chiudere la vecchia
  finestra. Non occorre indovinare una porta o modificare l’indirizzo a mano.
- “DLL load failed” su Windows: installa Visual C++ Redistributable x64
  dal link Microsoft indicato sopra; riapri Avvia ClipLab.cmd.
- Installazione/download incompleti: verifica Internet e spazio libero, poi
  ripeti Avvia o Aggiorna. Conserva il messaggio di errore preciso.
- Link YouTube rifiutato: prova un singolo video disponibile o il file originale.
  ClipLab non legge i cookie del browser e non aggira i blocchi della piattaforma.
- Trascrizione lenta: prova Base o Tiny, una sorgente breve e una sola clip.
- Dopo aver spostato la cartella, Python non parte: ferma il motore, rinomina
  SOLO .venv in .venv-precedente e riapri Avvia per ricreare l’ambiente.
  Mantieni .data, che contiene i tuoi progetti e i tuoi account.
- Su Windows avvia Diagnostica ClipLab.cmd per vedere quale componente fallisce.

10. VERSIONI E VERIFICHE

La versione è mostrata nell’app ed è definita in version.py.
Il registro dei cambiamenti è in CHANGELOG.md. Per aggiornare il programma
servono i file di un nuovo rilascio: “Aggiorna ClipLab” prepara solo i modelli.

Questa edizione Windows è stata preparata su Mac. Il codice condiviso e i
rami specifici per Windows sono verificati con test automatizzati; la prima
installazione e l’uso nativo su un PC Windows richiedono ancora verifica.
Non sono stati pubblicati contenuti reali durante i test.

11. SUGGERIMENTI E APPROVAZIONE SU GITHUB

Apri “Suggerimenti” nella barra laterale. Inserisci un titolo e descrivi il
risultato che vorresti ottenere. “Salva e invia a GitHub” conserva la proposta
sul computer e la mette in coda per il repository privato lucogol-source/ClipLab.
Quando GitHub la riceve, “Apri issue” porta alla discussione. Puoi chiudere
la scheda o riavviare l’app: la proposta resta nella cartella dati locale.

Sul Mac dello sviluppatore già configurato, Codex inoltra la coda all’account
collegato al prossimo controllo orario. Tieni il Mac sveglio e Codex aperto.
Su un altro Mac o PC Windows serve un account già invitato al repository.
Per l’invio automatico installa GitHub CLI da https://cli.github.com/ e avvia
questo comando nel Terminale del Mac o in PowerShell su Windows:

  gh auth login --hostname github.com --web

Completa nel browser l’accesso con il tuo account. In ClipLab premi “Riprova
ora”, oppure lascia acceso il motore per il tentativo automatico. La copia
per gli utenti usa le credenziali di GitHub CLI sul loro computer. L’issue
contiene titolo, descrizione, versione dell’app, sistema e ID della proposta.

Per lo sviluppatore
1) Apri https://github.com/lucogol-source/ClipLab/issues e leggi la proposta.
2) Dal tuo account lucogol-source, copia dal fondo dell’issue la riga che
   inizia con /cliplab approva e termina con il codice della proposta.
   Pubblicala da sola in un NUOVO commento, senza virgolette o backtick.
   Il codice identifica il testo esatto approvato. Se cambi la proposta,
   inviala come nuova proposta per ottenere il relativo comando.
3) Per ritirare l’approvazione aggiungi un nuovo commento con /cliplab revoca.
   Puoi anche chiudere l’issue. Se esiste già una pull request, puoi chiuderla.
4) Al controllo orario Codex verifica identità, repository, stato della
   proposta e commento. Per le proposte approvate prepara un ramo dedicato,
   esegue i test e apre una pull request collegata all’issue. La indica come
   bozza oppure come “[Da rivedere]” se il piano GitHub richiede una PR normale.
5) Vai su https://github.com/lucogol-source/ClipLab/pulls. Leggi il riepilogo
   e i risultati dei test in “Conversation”. In “Files changed” puoi esaminare
   ogni modifica e lasciare osservazioni. Merge e pubblicazione di una nuova
   versione restano decisioni dello sviluppatore.

Documentazione dei componenti gratuiti:
Python: https://www.python.org/
uv: https://docs.astral.sh/uv/
Node.js: https://nodejs.org/
Runtime JavaScript per YouTube: https://github.com/yt-dlp/yt-dlp/wiki/EJS

