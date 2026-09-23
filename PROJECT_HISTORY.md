# TRADING-BOT-V1 — STORIA COMPLETA DELLE VERSIONI E DEI TEST

Aggiornato: 23 settembre 2026

## Stato attuale

**Versione di riferimento / definitiva per ora:** `cvd-delta-strong-entry`.

Questa versione è il punto di riferimento corrente. Le varianti successive o alternative (ADX/regime, EMA50 e altre modifiche sperimentali) non sostituiscono la baseline corrente e vengono registrate qui come test separati.

> Nota sulla cronologia: la cronologia GitHub del repository inizia il 18/09/2026. Le fasi del 17/09 e i test eseguiti fuori dal repository sono ricostruiti dalle attività e dai risultati del progetto. Dove non è disponibile un risultato numerico verificabile, viene indicato esplicitamente.

---

# GIORNO 0 — 17/09/2026
## V1 iniziale: strategia candle-based

### Obiettivo
Creare un primo bot di trading/backtest con una logica basata principalmente su price action/candele e testare se esistesse un edge statistico.

### Approccio
La prima V1 utilizzava dati candle e logiche di breakout/mean-reversion, con gestione del rischio e diversi RR.

### Risultati baseline
I primi test hanno mostrato una performance fortemente negativa:

- Gennaio:
  - Return: **-69,89%**
  - Trade: **302**
  - Profit Factor: **0,335**
  - Drawdown: **69,74%**
- Febbraio:
  - Return: **-39,89%**
  - Trade: **148**
  - Profit Factor: **0,326**
  - Drawdown: **40,34%**

### Decisione
**SCARTATA.**

Motivo: la logica candle-only non mostrava un edge sufficiente. È stata quindi abbandonata come base definitiva.

---

# GIORNO 0 / PASSAGGIO SUCCESSIVO — 17/09/2026
## Sostituzione della V1 candle-based con V1 data-driven / order-flow

### Motivazione
Il progetto è stato spostato da una lettura prevalentemente candle-based verso una strategia quantitativa basata su dati di mercato.

### Dati/features introdotti
- Binance USD-M Futures
- aggTrades
- Delta buy/sell
- CVD
- volume
- relative volume
- z-score
- buy/sell ratio
- proxy Big Trade
- Volume Profile
- POC
- distanza dal POC
- score LONG/SHORT/FLAT
- test di diversi RR

### Elementi inizialmente considerati ma non implementati come dati storici affidabili
- OFI/DOM storico reale
- order-book depth storico
- liquidazioni storiche complete
- GEX/options storico

Motivo: disponibilità/qualità dei dati storici non sufficiente per costruire un test affidabile senza introdurre proxy non equivalenti al dato reale.

### Decisione
**IMPLEMENTATA come nuova direzione della V1.**

---

# 18/09/2026
## Primo ciclo di test RR della V1 order-flow

Sono stati testati diversi target RR, tra cui:

- 0,5R
- 0,75R
- 1R
- 1,25R
- 1,5R
- 2R

In un primo periodo di test (marzo) sono stati osservati:

| RR | Return | PF | Trade |
|---|---:|---:|---:|
| 0,5R | -4,83% | 0,961 | 773 |
| 0,75R | +1,58% | 1,010 | 773 |
| 1R | +8,14% | 1,043 | 773 |
| 1,25R | +19,21% | 1,087 | 773 |
| 1,5R | +17,43% | 1,074 | 773 |
| 2R | +18,31% | 1,067 | 773 |

### Interpretazione dell'epoca
1,25R risultava il miglior punto nel singolo periodo considerato, ma il risultato era ancora basato su un campione/periodo limitato e non veniva considerato sufficiente per dichiarare un edge definitivo.

### Decisione
**NON fissato un RR definitivo.**

Il progetto continua a testare la logica di ingresso prima di ottimizzare definitivamente il RR.

---

# 18/09/2026
## Logging e analisi delle operazioni

Sono stati aggiunti/rafforzati:

- trade log completo
- CSV separati per RR
- MFE
- MAE
- direzione
- score
- motivazioni
- entry/exit
- PnL
- outcome
- durata
- CVD
- Delta
- volume
- Big Trade
- VWAP
- POC/distanza POC
- exit reason
- eventi di partial
- BE
- trailing
- struttura del trade

### Decisione
**IMPLEMENTATA.**

Obiettivo: rendere possibile analizzare non solo il risultato finale, ma anche perché ogni trade è entrato e come si è comportato.

---

# 18/09/2026
## Prima V1 order-flow completa

La strategia order-flow iniziale viene progressivamente resa più selettiva.

La direzione del progetto diventa:

**Market data → feature order-flow → segnale → backtest → analisi statistica.**

La logica viene poi sottoposta a filtri specifici su CVD, Delta e Big Trade.

---

# 21/09/2026
# VERSIONE CVD-ONLY / RESULTS1

## Modifica
Viene introdotto il CVD come conferma del segnale, riducendo il peso della logica precedente.

### Test
RR1:

- Trade: **167**
- Return: **-8,34%**
- Profit Factor: **0,812**
- Drawdown: **10,98%**

### Decisione
**SCARTATA come versione di riferimento.**

Motivo: il CVD da solo non era sufficiente a produrre un risultato soddisfacente.

---

# 21/09/2026
# VERSIONE CVD-STRONG-ENTRY / RESULTS2

## Modifica
Il CVD viene trasformato da semplice informazione/score a **filtro di ingresso forte**.

La logica cerca di entrare solo quando il CVD fornisce una conferma più significativa.

### Risultati RR 0,5–2R

| RR | Return | PF | Win rate | Trade |
|---|---:|---:|---:|---:|
| 0,5R | -6,60% | 0,694 | 58,1% | 105 |
| 0,75R | -6,27% | 0,750 | 50,0% | 102 |
| 1R | -3,56% | 0,868 | 46,5% | 101 |
| 1,25R | -4,43% | 0,851 | 40,6% | 101 |
| 1,5R | -8,31% | 0,732 | 33,0% | 97 |
| 2R | -6,02% | 0,811 | 28,9% | 90 |

RR1:
- LONG PF: **0,674**
- SHORT PF: **1,001**

### Decisione
**SUPERATA / SCARTATA come baseline successiva.**

Motivo: il filtro CVD forte migliorava la selezione rispetto a CVD-only in alcuni aspetti, ma il risultato complessivo restava negativo.

---

# 21/09/2026
# VERSIONE CVD + DELTA STRONG ENTRY — PRIMO TEST

## Modifica
Vengono aggiunti insieme:

- CVD forte
- Delta forte

Obiettivo: evitare ingressi in cui il CVD è favorevole ma il flusso aggressivo non conferma.

### Primo test con soglie Delta/CVD ±2
RR1:

- Trade: **49**
- Return: **-3,50%**
- PF: **0,749**
- Drawdown: **5,87%**
- LONG: 12 trade, PF **0,720**
- SHORT: 37 trade, PF **0,759**

### Decisione
**NON adottata in questa forma.**

Motivo: il filtro era troppo selettivo e il risultato non era ancora positivo.

---

# 21/09/2026
## Variante Delta ±2 + CVD ±1,5

### Modifica
Per verificare se la soglia CVD ±2 fosse eccessivamente restrittiva:

- Delta: ±2
- CVD: ±1,5

### Risultato RR1
- Trade: **63**
- Return: **-2,55%**
- PF: **0,852**
- Drawdown: **7,27%**
- LONG: 17 trade, PF **0,888**
- SHORT: 46 trade, PF **0,839**

### Decisione
**SCARTATA come configurazione definitiva.**

Risultava migliore del test ±2/±2 in alcuni parametri, ma restava negativa.

---

# 21/09/2026
# CVD-DELTA-STRONG-ENTRY — SVILUPPO

La struttura viene ulteriormente raffinata.

### Modifiche tecniche
- CVD strong-entry filter
- rimozione del volume scoring
- utilizzo di una pendenza CVD multi-bar
- correzione del consumo del signal dictionary nel backtest engine

Commit principali:
- `3e51270` — CVD strong entry filter e rimozione volume scoring
- `302217c` — multi-bar CVD slope
- `4893ec2` — correzione signal dict nel backtest

Questa diventa la base della branch:

**`cvd-strong-entry`**

---

# 21/09/2026
# TEST FINALE DELLA BRANCH CVD-STRONG-ENTRY

La versione CVD strong-entry viene mantenuta come base tecnica, ma viene ulteriormente sottoposta a test sulle soglie Delta/CVD.

---

# 21/09/2026
# CVD-DELTA ±2 — TEST

### Configurazione
- Delta threshold: **±2**
- CVD threshold: **±2**

### Risultato RR1
- Trade: **49**
- Return: **-3,50%**
- PF: **0,749**

Questa configurazione è quindi troppo restrittiva nel periodo iniziale.

---

# 21/09/2026
# CVD-DELTA ±2 / CVD ±1,5 — TEST

### Configurazione
- Delta: **±2**
- CVD: **±1,5**

### Risultato RR1
- Trade: **63**
- Return: **-2,55%**
- PF: **0,852**

Anche questa configurazione non viene mantenuta come definitiva.

---

# 21/09/2026
# CVD-DELTA-STRONG-ENTRY — CONFIGURAZIONE DEFINITIVA DI RIFERIMENTO

La branch viene denominata:

**`cvd-delta-strong-entry`**

Testata con:
- Delta threshold ±2
- CVD threshold testate
- CVD multi-bar slope
- strong entry filter
- volume scoring rimosso

Il test successivo su un campione più ampio diventa il riferimento principale.

---

# 22/09/2026
# TEST EMA50 — BRANCH EMA

## Obiettivo
Provare un filtro direzionale di regime:

**EMA50 come filtro obbligatorio della direzione.**

La logica prevedeva inoltre una conferma più rigida del cambio bias tramite più candele M5.

### Motivazione
Verificare se l'EMA50 potesse eliminare trade contro il movimento dominante.

### Risultato test 01/04–08/04
Nel confronto RR0,75:

- versione con EMA: **-7,74%**, 451 trade
- versione senza EMA: **+1,11%**, 555 trade

Il filtro EMA riduceva i trade ma peggiorava il risultato nel campione testato.

### Decisione
**SCARTATA.**

Successivamente l'EMA viene esplicitamente rimossa dal progetto.

**EMA DA CONSIDERARE ABANDONATA E NON PARTE DELLA STRATEGIA CORRENTE.**

---

# 23/09/2026
# TEST ADX / REGIME

## Obiettivo
Capire se il bot potesse riconoscere il regime di mercato e operare in modo diverso in:

- trend/continuation
- bassa forza / mean-reversion

### Variante testata
ADX + contesto/regime.

### Risultati 3 mesi

Confronto tra baseline `cvd-delta-strong-entry` e ADX + contesto:

| RR | Baseline Return | Baseline PF | ADX Return | ADX PF |
|---|---:|---:|---:|---:|
| 0,5R | -8,26% | 0,915 | +3,38% | 1,030 |
| 0,75R | +1,11% | 1,009 | +3,58% | 1,026 |
| 1R | +6,53% | 1,048 | +11,32% | 1,075 |
| 1,25R | +19,77% | 1,131 | +20,68% | 1,124 |
| 1,5R | +24,63% | 1,154 | +16,95% | 1,098 |
| 2R | +23,67% | 1,141 | +10,11% | 1,058 |

Trade count baseline vs ADX:

- RR0,5: 576 vs 684
- RR0,75: 555 vs 655
- RR1: 538 vs 623
- RR1,25: 527 vs 604
- RR1,5: 509 vs 574
- RR2: 480 vs 539

### Ulteriore analisi ADX <20

Mean-reversion:
- 216 trade
- PF **0,914**
- expectancy **-2,69**

Continuation:
- 404 trade
- PF **1,142**
- expectancy **+4,06**

### Decisione
**NON adottato come sostituzione della baseline.**

Motivo: l'ADX/regime mostra informazione interessante sul comportamento del mercato, ma non giustifica la sostituzione della struttura principale. In particolare, il vantaggio della variante ADX dipende dal RR e la baseline CVD-Delta mantiene risultati più forti a RR1,5 e RR2 nel confronto considerato.

Il test viene quindi conservato come ricerca separata.

---

# 23/09/2026
# BIG TRADE — ANALISI

Il Big Trade viene analizzato come possibile conferma aggiuntiva.

### RR1,5 — analisi su 161 trade

Tutti:
- 161 trade
- PF **1,213**
- expectancy **+0,118R**

Con Big Trade:
- 3 trade
- PF **0,749**
- expectancy **-0,167R**
- risultato totale: **-0,5R**

Senza Big Trade:
- 158 trade
- PF **1,224**
- expectancy **+0,123R**

### Delta/CVD vs Big Trade
- BIG + Delta/CVD: 2 trade
- Win rate: 50%
- PF: **1,50**
- Expectancy: **+0,25R**
- Delta+CVD senza Big Trade: 77 trade
- Win rate: **51,95%**
- PF: **1,622**
- Expectancy: **+0,299R**
- Big Trade contro flow: 1 trade, **-1R**

### Decisione
**Big Trade NON promosso a filtro obbligatorio.**

Motivo: campione troppo piccolo e, nel campione analizzato, il Big Trade non aggiungeva un miglioramento robusto alla struttura Delta/CVD.

I dati Big Trade restano utili per analisi future, ma non modificano la baseline.

---

# TEST ABSORPTION / ANALISI_ABSORPTION

## Obiettivo
Aggiungere un'informazione simile all'assorbimento order-flow.

### Implementazione
È stato creato un modulo di absorption/order-flow.

### Limite fondamentale
Lo storico disponibile non forniva un vero order book depth storico completo.

Di conseguenza l'assorbimento è stato trattato come **proxy**, non come vera misura storica della liquidità passiva.

### Decisione
**NON promosso a filtro core della strategia.**

Motivo: il proxy non è equivalente a un vero storico bid/ask depth/DOM. Inserirlo come regola obbligatoria avrebbe introdotto un rischio metodologico maggiore rispetto al beneficio dimostrabile.

Il modulo resta come ricerca sperimentale.

---

# VOLUME SCORING — TEST E RIMOZIONE

Il volume era inizialmente incluso nello scoring del segnale.

Successivamente, durante la costruzione di CVD strong-entry, il volume scoring è stato rimosso.

### Motivo
Il progetto viene spostato verso una logica più pulita:

**Delta + CVD → conferma del flusso**

anziché accumulare molti punti provenienti da feature correlate.

### Decisione
**SCARTATO come componente dello score principale.**

---

# OFI / DOM / LIQUIDATIONS / GEX

Sono stati considerati come possibili estensioni del bot.

### Problema
Per il backtest storico gratuito disponibile non erano presenti dati sufficientemente affidabili e completi per trattarli come dati reali.

### Decisione
**NON IMPLEMENTATI come core della V1.**

Non vengono considerati feature obbligatorie della versione attuale.

---

# ORGANIZZAZIONE DEL REPOSITORY — 18/09/2026

Il progetto è stato organizzato nel repository:

`aalzaa/trading-bot-v1`

Modifiche principali:

- organizzazione dei file in directory
- trade log RR1,5 spostato in `data`
- `orderflow.py` spostato in `features`
- `signal.py` spostato in `strategy`
- rimozione dei file root duplicati dopo lo spostamento

Queste modifiche sono organizzative e **non rappresentano cambiamenti di strategia**.

---

# BRANCH PRINCIPALI E LORO SIGNIFICATO

## main
Branch di riferimento del repository.

Contiene l'organizzazione generale del progetto e la documentazione.

## cvd-only-divergence
Esperimento:
- CVD trend
- CVD divergence
- rimozione del delta score

**Stato: SCARTATO come baseline.**

## cvd-strong-entry
Esperimento:
- CVD strong-entry
- multi-bar CVD slope
- volume scoring rimosso

**Stato: SUPERATO da CVD + Delta.**

## cvd-delta-strong-entry
Versione:
- CVD strong-entry
- Delta strong-entry
- soglie testate
- multi-bar CVD slope
- volume scoring rimosso

**Stato: VERSIONE DI RIFERIMENTO / DEFINITIVA PER ORA.**

## results3
Contiene i risultati del ciclo CVD/Delta/Big Trade su 3 mesi.

## results4
Contiene i risultati dell'esperimento ADX + contesto/regime.

---

# RISULTATO CORRENTE DI RIFERIMENTO — 3 MESI

La baseline `cvd-delta-strong-entry` ha prodotto:

| RR | Return | PF |
|---|---:|---:|
| 0,5R | -8,26% | 0,915 |
| 0,75R | +1,11% | 1,009 |
| 1R | +6,53% | 1,048 |
| 1,25R | +19,77% | 1,131 |
| 1,5R | **+24,63%** | **1,154** |
| 2R | +23,67% | 1,141 |

Trade:

- 0,5R: 576
- 0,75R: 555
- 1R: 538
- 1,25R: 527
- 1,5R: 509
- 2R: 480

Questo è il risultato di riferimento attuale del progetto, non una garanzia di performance futura.

---

# DECISIONI DEFINITIVE FINORA

## SCARTATI

1. Candle-only V1
2. Breakout/mean-reversion candle baseline
3. CVD-only
4. CVD divergence come unico filtro
5. CVD strong-entry senza Delta
6. Delta/CVD ±2 nel primo campione
7. Delta ±2 + CVD ±1,5 come configurazione finale
8. Volume scoring
9. Big Trade come filtro obbligatorio
10. Absorption proxy come filtro obbligatorio
11. EMA50 come filtro direzionale obbligatorio
12. ADX mean-reversion/regime come sostituzione della baseline
13. OFI/DOM storico reale come feature core, per mancanza di dati storici adeguati
14. Liquidations/GEX storico come feature core, per mancanza di dati storici adeguati

## IMPLEMENTATI / MANTENUTI

1. Data-driven/order-flow V1
2. Binance Futures aggTrades
3. Delta
4. CVD
5. CVD multi-bar slope
6. Strong-entry filtering
7. Delta strong-entry
8. Volume Profile / POC
9. trade logging completo
10. MFE/MAE
11. analisi per RR
12. analisi Big Trade come ricerca
13. analisi regime come ricerca separata

---

# STATO DEL PROGETTO AL 23/09/2026

**BASELINE CORRENTE: `cvd-delta-strong-entry`**

La baseline non deve essere modificata semplicemente aggiungendo nuovi indicatori.

Ogni nuova modifica deve essere trattata come **esperimento separato**, confrontato contro questa baseline sugli stessi dati e sullo stesso periodo.

La baseline attuale è quindi il punto zero per i prossimi test.

---

# CRONOLOGIA GIT RECENTE

18/09:
- `4a4a72c` — inizializzazione/upload dei file
- `cde2249` — organizzazione dei file
- `60dc272` — spostamento del trade log RR1,5 in data
- `428ecea` — upload dei file
- `c6e2a73` — orderflow.py → features
- `7f0e0b4` — signal.py → strategy
- `f9f9180` — rimozione orderflow.py root
- `69d055b` — rimozione signal.py root

21/09:
- `3e51270` — CVD strong-entry + rimozione volume scoring
- `302217c` — multi-bar CVD slope
- `4893ec2` — fix signal dict
- `68decf0` — CVD trend/divergence
- `feab9bf` — rimozione delta score + CVD divergence
- `5b7fbff` — logging CVD confirmations
- `ad11170` — fix structure backtest
- `8d007ae` — Delta/CVD thresholds ±2
- `575bc0f` — note branch
- `c92d01d` — Delta ±2 / CVD ±1,5

21–23/09:
- branch `cvd-delta-strong-entry` usata come riferimento
- risultati 3 mesi salvati/analizzati in `results3`
- test ADX/regime separato in `results4`
- EMA50 testata e poi scartata
- Big Trade analizzato senza promozione a filtro obbligatorio

---

# REGOLA DI VERSIONING DA QUESTO MOMENTO

**Baseline congelata: `cvd-delta-strong-entry`.**

Ogni nuova idea deve:

1. partire dalla baseline;
2. avere una branch separata;
3. mantenere invariato il dataset di confronto;
4. mantenere invariata la gestione del backtest;
5. riportare RR, trade, return, PF, win rate, expectancy e DD quando disponibili;
6. essere confrontata direttamente con la baseline;
7. essere scartata se non dimostra un miglioramento robusto;
8. non modificare la baseline finché il test non è concluso.

Fine del registro corrente.


---

# 23/09/2026
# DECISIONE FINALE — ADX/REGIME, BIG TRADE + ABSORPTION

## ADX / REGIME — SCARTATI

Dopo il confronto sui 3 mesi, l'esperimento ADX + contesto/regime viene **scartato come componente della strategia corrente**.

### Motivo operativo

L'ADX/regime tende a limitare il comportamento della baseline nei periodi in cui il bot riesce a produrre i maggiori profitti, mentre introduce anche una maggiore frequenza di stop/operazioni non vantaggiose nel confronto complessivo.

In particolare, il beneficio del filtro non è stabile al variare del RR e, rispetto alla baseline, riduce il potenziale profitto nei RR più importanti per la struttura attuale.

### Decisione

**ADX e classificazione di regime vengono abbandonati come filtri della strategia.**

Restano eventualmente disponibili solo come materiale di ricerca/analisi, ma **non fanno parte della versione cvd-delta-strong-entry**.

---

# 23/09/2026
# BIG TRADE + ABSORPTION — MANTENUTI NELLA VERSIONE CORRENTE

È stato rivalutato l'utilizzo congiunto di:

- Big Trade
- Absorption

L'obiettivo non è aumentare direttamente il profitto lordo, ma verificare se queste informazioni migliorano la **qualità e la distribuzione del rischio** del sistema.

### Risultato osservato

Il test non mostra un aumento significativo del profitto rispetto alla baseline.

Tuttavia, l'informazione combinata Big Trade + Absorption:

- **riduce sensibilmente il drawdown**;
- **aumenta il Profit Factor**;
- migliora il profilo di rischio del sistema;
- non viene utilizzata per cercare di aumentare artificialmente il numero di trade o il profitto.

Quindi il loro valore viene considerato principalmente come **filtro/controllo di qualità e rischio**, non come motore aggiuntivo di rendimento.

### Decisione

**MANTENUTI nella versione cvd-delta-strong-entry.**

Questa decisione modifica la valutazione precedente in cui Big Trade e Absorption erano considerati separatamente come non sufficienti a giustificare un filtro obbligatorio.

La configurazione corrente viene quindi considerata:

**CVD + Delta Strong Entry + Big Trade + Absorption**

con l'obiettivo di mantenere l'edge della baseline migliorando il profilo di drawdown/PF.

> Nota metodologica: i valori numerici specifici del miglioramento di DD e PF devono essere aggiunti al registro quando viene salvato il relativo CSV/JSON definitivo del test. In questa voce viene registrata la decisione e il risultato qualitativo comunicato nel test.

---

# STATO AGGIORNATO AL 23/09/2026

**VERSIONE CORRENTE: cvd-delta-strong-entry**

Componenti mantenute:

1. Delta
2. CVD
3. CVD multi-bar slope
4. Strong-entry filtering
5. Volume Profile / POC
6. Big Trade
7. Absorption
8. logging completo
9. MFE/MAE
10. analisi per RR

Componenti definitivamente escluse dalla strategia corrente:

1. EMA50
2. ADX / regime filter
3. volume scoring
4. CVD-only
5. CVD divergence-only
6. altre varianti precedenti non confermate

La baseline rimane congelata come riferimento. Big Trade e Absorption sono ora considerati parte della configurazione corrente perché il loro beneficio principale è sul **drawdown e sul Profit Factor**, non sull'aumento del profitto assoluto.

---

# REGOLA AGGIORNATA PER I PROSSIMI TEST

Il prossimo test deve partire dalla configurazione corrente:

**cvd-delta-strong-entry = CVD + Delta + Big Trade + Absorption**

ADX/regime ed EMA non devono essere reintrodotti come filtri, salvo un nuovo esperimento esplicitamente separato.


---

Fine del registro corrente.
