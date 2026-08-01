# Guide utilisateur ZolaOS

*Tutoriel pas-à-pas pour les équipes qui utilisent ZolaOS au quotidien — côté client (Zolabox) et côté cabinet Polaris (Zolacortex).*

---

## Sommaire

1. [Bienvenue](#1-bienvenue)
2. [Premiers pas](#2-premiers-pas)
3. [Zolabox — utiliser l'assistant et les modules](#3-zolabox--utiliser-lassistant-et-les-modules)
4. [Zolacortex — conduire une mission de A à Z](#4-zolacortex--conduire-une-mission-de-a-à-z)
5. [Les 7 assistants IA du cabinet](#5-les-7-assistants-ia-du-cabinet)
6. [Bonnes pratiques & FAQ](#6-bonnes-pratiques--faq)
7. [Aide & support](#7-aide--support)
8. [Glossaire](#8-glossaire)

---

## 1. Bienvenue

### 1.1 C'est quoi ZolaOS ?

ZolaOS est une plateforme d'intelligence artificielle **souveraine** (tout tourne en local, aucune donnée ne part vers un service cloud externe) qui rassemble, au même endroit, un assistant conversationnel et des modules métier (droit, comptabilité/RH, santé, cybersécurité/conformité, microfinance…). Elle a été conçue pour les besoins des entreprises et administrations de la République du Congo, en s'appuyant sur le droit OHADA et le droit congolais.

### 1.2 Deux faces, une même plateforme

ZolaOS se présente sous **deux visages**, qui partagent le même moteur mais ne voient jamais les mêmes données :

| | **Zolabox** | **Zolacortex** |
|---|---|---|
| Pour qui | Les équipes de l'entreprise cliente | Les équipes du cabinet Polaris |
| À quoi ça sert | Poser des questions, utiliser les modules métier, gérer ses propres documents | Piloter les missions du cabinet pour ses clients (temps, livrables, honoraires, pilotage) |
| Données visibles | Uniquement celles de l'entreprise cliente | Les données du cabinet ; jamais un accès direct aux données du client en dehors du cadre strict d'une mission |

> **À retenir — Zero Trust.** Le cabinet n'a pas de « porte dérobée » vers les données du client. Tout accès depuis Zolacortex vers des données client se fait dans le cadre encadré, tracé et limité dans le temps d'une mission.

Ce guide couvre les deux faces : la section 3 s'adresse aux utilisateurs de Zolabox, la section 4 aux équipes du cabinet sur Zolacortex.

### 1.3 À qui s'adresse ce guide ?

À toute personne qui **utilise** ZolaOS au quotidien pour son travail — pas aux équipes techniques qui l'installent ou la maintiennent. Aucune connaissance en informatique ou en intelligence artificielle n'est nécessaire.

### 1.4 Les 4 principes de l'IA de ZolaOS

Avant de commencer, quatre règles simples gouvernent tout ce que fait l'IA dans ZolaOS. Elles reviendront tout au long de ce guide.

1. **Locale et souveraine** — les modèles d'IA tournent sur des serveurs contrôlés par la plateforme (chez le client ou chez Polaris selon la face utilisée). Aucune question, aucun document n'est envoyé à un service d'IA sur Internet.
2. **Elle cite ses sources** — chaque réponse ancrée s'appuie sur des documents identifiables (textes de loi, procédures internes, référentiels…) que vous pouvez ouvrir et vérifier.
3. **Elle s'abstient plutôt que d'inventer** — si le corpus disponible ne couvre pas votre question, l'assistant le dit clairement au lieu de répondre au hasard.
4. **L'humain valide** — l'IA rédige des **projets** (de note, de texte, de proposition, de compte rendu). Rien n'est enregistré, publié ou envoyé sans une action explicite de votre part. Les montants (prix, honoraires, marges, bulletins de paie…) sont toujours **calculés** par le moteur, jamais « inventés » par l'IA.

---

## 2. Premiers pas

### 2.1 Se connecter

1. Ouvrez votre navigateur et rendez-vous sur l'adresse de votre instance ZolaOS (en environnement de démonstration : `http://localhost:3000`).
2. Sur l'écran de connexion, saisissez votre **email** et votre **mot de passe**.
3. Cliquez sur **Se connecter**.

> En environnement de démonstration/formation, un compte est fourni par votre référent (par exemple `admin@polaris.cg`). En production, chaque personne dispose de son propre compte nominatif — ne partagez jamais vos identifiants.

Si vos identifiants sont incorrects, un message l'indique clairement. Après plusieurs tentatives infructueuses, la connexion est temporairement bloquée par sécurité : patientez quelques minutes avant de réessayer.

### 2.2 Comprendre l'écran d'accueil

Une fois connecté, vous arrivez sur le **tableau de bord**. La structure de l'écran est la même partout dans l'application :

- **À gauche**, une barre de navigation (la « sidebar ») liste les écrans auxquels vous avez accès. Son contenu change selon que vous êtes sur Zolabox ou sur Zolacortex, et selon votre rôle.
- **Au centre**, le contenu de l'écran sélectionné.
- **En bas à droite** (sur Zolabox), une bulle **Assistant** flottante permet de poser une question à tout moment, sans quitter l'écran où vous travaillez.

### 2.3 Les rôles

ZolaOS distingue trois rôles, qui déterminent ce que vous pouvez voir et faire :

| Rôle | Description |
|---|---|
| **admin** | Équipe de direction du cabinet Polaris. Accès complet à Zolacortex : pilotage, supervision, plan de charge, honoraires, alertes marge, clients, comptes, facturation, journal d'audit. |
| **consultant** | Équipe opérationnelle du cabinet. Accès aux écrans de production courante (missions, pipeline, feuilles de temps, notes de frais, livrables) mais pas aux écrans de pilotage/gestion réservés aux administrateurs. |
| **client** | Utilisateur de l'entreprise cliente, côté Zolabox. Accès à l'assistant et aux modules métier de son organisation uniquement. |

Si un écran ou un bouton vous semble manquant, c'est probablement une question de rôle — voir la [FAQ](#6-bonnes-pratiques--faq).

### 2.4 Se déconnecter

Pour terminer votre session en toute sécurité (recommandé sur un poste partagé), utilisez l'option de déconnexion de l'application. Vous serez redirigé vers l'écran de connexion.

---

## 3. Zolabox — utiliser l'assistant et les modules

### 3.1 Poser une bonne question

L'assistant répond d'autant mieux qu'on lui pose une question précise. Quelques réflexes utiles :

1. **Situez le contexte** : plutôt que « quel est le préavis ? », préférez « quel est le préavis de licenciement pour un cadre en CDI avec 5 ans d'ancienneté ? ».
2. **Une question à la fois** : si vous avez plusieurs questions, posez-les l'une après l'autre — les réponses n'en seront que plus claires.
3. **Utilisez un module** quand c'est possible (voir 3.5) : l'assistant est alors pré-orienté vers le bon domaine, ce qui améliore la pertinence de la réponse.

Pour accéder à l'assistant en plein écran, utilisez l'entrée **Assistant** de la barre de navigation. Sur les écrans de module, une bulle **Assistant** flottante en bas à droite offre le même service sans changer de page.

### 3.2 Lire une réponse : citations et ancrage

Une réponse de l'assistant se compose de plusieurs éléments :

1. **Le texte de la réponse**, rédigé en français clair.
2. **Les sources citées**, sous forme de petites étiquettes `[1]`, `[2]`… en dessous du message. Cliquez sur une source pour l'ouvrir dans la Bibliothèque documentaire et vérifier le texte exact dont l'IA s'est servie.
3. **Un badge d'avertissement**, visible uniquement quand la réponse n'a *aucune* source à l'appui (« Réponse non sourcée — à vérifier »). Dans ce cas, traitez la réponse avec prudence : vérifiez toute règle, tout chiffre ou toute référence avant de vous en servir.
4. **Un retour utile/pas utile** sous chaque réponse, pour aider à améliorer l'assistant dans la durée.

> **Bien utiliser l'IA de ZolaOS**
> - Une réponse **avec sources** peut être vérifiée en un clic : ouvrez la source, comparez.
> - Une réponse **sans source** (badge orange) n'est pas une réponse fiable en l'état : elle doit être recoupée avant toute utilisation.
> - Si l'assistant **s'abstient** (il l'indique explicitement), ce n'est pas une panne : cela signifie que le corpus disponible ne couvre pas votre question. Reformulez, précisez, ou signalez le manque à votre référent pour enrichissement du corpus.

### 3.3 La réponse « approfondie »

Pour les questions qui méritent une analyse plus poussée, un commutateur **Réponse approfondie (70B, plus lent)** est disponible dans la bulle d'assistant contextuel. Il active un modèle d'IA plus puissant mais nettement plus lent (jusqu'à une à deux minutes de réponse). À réserver aux questions complexes où la rapidité importe moins que la profondeur d'analyse.

### 3.4 Téléverser vos propres documents

Vous pouvez enrichir les réponses de l'assistant avec vos propres documents (règlement intérieur, statuts, grille salariale, procédures internes…) :

1. Ouvrez l'écran **Consultation** (Bibliothèque documentaire) depuis la barre de navigation.
2. Sélectionnez l'onglet **Mes documents**.
3. Choisissez le module concerné (RH/Droit du travail, Comptabilité, Juridique, Fiscal, Projets ONG…) et le type de document.
4. Téléversez le fichier.

> Ces documents restent **cloisonnés à votre organisation** : ils n'enrichissent que les réponses données à vos équipes, jamais celles d'une autre organisation.

### 3.5 Tour des modules métier

Chaque module donne accès à des écrans dédiés et à un assistant pré-orienté sur son domaine. Les modules disponibles dépendent de votre organisation ; les grandes familles sont :

| Pôle | Exemples de modules |
|---|---|
| **Droit** | Droit OHADA (sociétés, sûretés, contrats), droit du travail congolais, droit fiscal (CGI), droit administratif |
| **ERP & Opérations** | Comptabilité (SYSCOHADA/AUDCIF), paie, RH (référentiels, recrutement, formation), finance/trésorerie, achats, supply chain, moyens généraux |
| **Santé** | Pharmacologie (posologie, interactions, information médicament) |
| **Cyber / GRC** | Audit de configuration et durcissement défensif, conformité |
| **Fintech** | Scoring crédit, KYC, surveillance AML (microfinance) |

Pour ouvrir un module, cliquez sur son intitulé dans la barre de navigation (regroupé par pôle). Chaque écran de module propose des actions propres à son métier (par exemple : simuler un bulletin de paie, valider une écriture comptable) en plus de l'assistant contextuel.

### 3.6 Assistant code souverain (clients tech)

Pour les organisations qui en disposent, un module spécifique indexe le code source du client afin de répondre à des questions dessus (explication, debug, revue). Le code ne quitte jamais les murs de l'organisation.

---

## 4. Zolacortex — conduire une mission de A à Z

Cette section suit le parcours complet d'une mission de conseil pour le cabinet Polaris, du premier contact commercial jusqu'au pilotage de la rentabilité. Nous prenons comme fil rouge une **mission d'audit** (par exemple un audit de conformité RH), mais le principe est identique pour toute autre offre.

La chaîne de valeur, dans l'ordre où on la traverse :

```
Pipeline (CRM) → Mission → Plan de charge → Feuilles de temps + Notes de frais
   → Livrables → Honoraires → Pilotage / Alertes marge
```

### 4.1 Pipeline — suivre l'opportunité commerciale

1. Ouvrez **Pipeline** dans la barre de navigation.
2. Créez une nouvelle opportunité : titre, offre (par exemple *audit_commercial*), montant estimé, date de clôture prévisionnelle.
3. Faites-la avancer dans les étapes : **Prospect → Qualifié → Proposition → Gagné/Perdu**.
4. À l'étape « Proposition », vous pouvez rédiger une lettre de mission — voir [5.2](#52-rédaction-de-proposition).
5. Une fois l'opportunité **gagnée**, convertissez-la en mission.

### 4.2 Missions — le dossier de référence

L'écran **Missions** liste les missions actives, révoquées, expirées ou terminées. Chaque mission rattache un client, une offre et un périmètre. C'est la mission qui sert de point d'ancrage à toutes les étapes suivantes (temps, livrables, honoraires).

### 4.3 Plan de charge — affecter les consultants

*(Réservé aux administrateurs.)*

1. Ouvrez **Plan de charge**.
2. Affectez un consultant à la mission, semaine par semaine.
3. La vue agrégée compare la charge planifiée à la capacité disponible de chaque consultant, pour repérer les sur- ou sous-charges avant qu'elles ne posent problème.

### 4.4 Feuilles de temps — enregistrer le travail réalisé

1. Ouvrez **Feuilles de temps**.
2. Dans **Ma feuille de temps**, sélectionnez la mission, la date, la durée et l'activité, puis enregistrez la ligne.
3. Chaque ligne suit un statut (brouillon → soumise → …) jusqu'à son approbation.
4. Pour gagner du temps, utilisez la **saisie assistée par IA** — voir [5.5](#55-saisie-de-temps-assistée).

### 4.5 Notes de frais

Ouvrez **Notes de frais** pour déclarer les débours de mission (déplacements, hébergement…), qui viendront s'ajouter aux honoraires lors de la facturation.

### 4.6 Livrables — produire et faire relire les documents de mission

1. Ouvrez **Livrables** et sélectionnez la mission.
2. Créez un livrable (à partir d'un modèle ou vierge).
3. Rédigez-le vous-même, ou demandez un **projet rédigé par l'IA** — voir [5.1](#51-rédaction-de-livrable).
4. Avant de le finaliser, utilisez **Relire (IA)** pour une revue qualité — voir [5.3](#53-relecture-qualité).
5. Faites évoluer son statut : **brouillon → en relecture → final**.

C'est également depuis cet écran que se génèrent la **note de recherche / mémo réglementaire** ([5.4](#54-mémo-réglementaire)) et la **synthèse d'entretien** ([5.7](#57-synthèse-dentretien)), toutes deux enregistrées comme livrables de la mission sélectionnée.

### 4.7 Honoraires — facturer la mission

*(Réservé aux administrateurs.)*

1. Ouvrez **Honoraires**.
2. Le cabinet regroupe les feuilles de temps facturables approuvées de la mission (plus les notes de frais) en une facture.
3. La facture suit un cycle de statuts : **brouillon → émise → payée** (ou annulée).
4. L'écran d'**échéancier** (aging) classe les factures émises par ancienneté (à échoir, 1-30 j, 31-60 j, 61-90 j, +90 j) pour prioriser les relances.

### 4.8 Pilotage et Alertes marge — surveiller la rentabilité

*(Réservés aux administrateurs.)*

- **Pilotage** rassemble les indicateurs clés du cabinet (KPI) toutes missions confondues.
- **Alertes marge** détecte automatiquement les missions en marge négative, en marge faible, ou en sous-facturation (encours non facturé), avec le montant d'impact estimé pour chacune. Depuis cet écran, une **note de pilotage (IA)** peut résumer et prioriser ces alertes — voir [5.6](#56-alertes-marge--sous-facturation).

### 4.9 Autres écrans utiles

| Écran | À quoi il sert |
|---|---|
| **Supervision** | Vue d'ensemble transverse du cabinet (admin) |
| **Clients** | Annuaire des organisations clientes |
| **Comptes** | Gestion des comptes utilisateurs du cabinet (admin) |
| **Journal d'audit** | Traçabilité des actions effectuées dans Zolacortex (admin) |

---

## 5. Les 7 assistants IA du cabinet

Zolacortex intègre sept assistants IA spécialisés, chacun greffé sur une étape précise de la chaîne de mission. Tous partagent la même doctrine : **l'IA propose, l'humain valide**. Chaque appel renvoie l'un de ces trois statuts, jamais une erreur brute :

| Statut | Signification |
|---|---|
| **Généré** | Un projet a été produit ; il est affiché pour relecture/validation. |
| **Abstention** | Le corpus disponible ne couvre pas assez le sujet ; rien n'a été rédigé plutôt que d'inventer. |
| **Indisponible** | Le service d'IA est momentanément hors service ; réessayez plus tard. |

### 5.1 Rédaction de livrable

**À quoi ça sert.** Obtenir un premier projet rédigé pour un livrable de mission (note, rapport…), ancré sur le corpus documentaire et cité.

**Comment faire.**
1. Ouvrez le livrable concerné dans **Livrables**.
2. Cliquez sur **Générer un projet (IA)**.
3. Relisez le projet proposé, avec ses sources citées.
4. Le contenu n'est écrit dans le livrable qu'après votre validation.

**Ce que l'IA fait / ne fait pas.** Elle rédige un texte cité, ancré sur le corpus disponible. Elle ne remplace pas votre jugement professionnel et ne publie rien sans validation explicite.

### 5.2 Rédaction de proposition

**À quoi ça sert.** Générer une lettre de mission (proposition commerciale) ancrée sur le corpus réglementaire, depuis une opportunité du pipeline.

**Comment faire.**
1. Sur l'opportunité concernée (écran **Pipeline**), ouvrez la section **Proposition commerciale**.
2. Cliquez sur **Rédiger la proposition (IA)**.
3. Relisez et complétez si besoin, puis **Enregistrer**.

**Ce que l'IA fait / ne fait pas.** Elle rédige le contexte réglementaire ancré et cité. Elle **ne chiffre jamais les honoraires** : le montant de la proposition reste une décision humaine à part entière.

### 5.3 Relecture qualité

**À quoi ça sert.** Faire contrôler un livrable déjà rédigé contre les textes de référence, avant de le finaliser.

**Comment faire.**
1. Sur le livrable, cliquez sur **Relire (IA)**.
2. Le résultat s'affiche sous forme de verdict : *Bien étayé* / *À vérifier — non étayé* / *Points manquants*.

**Ce que l'IA fait / ne fait pas.** Elle confronte le texte du livrable au corpus et signale les écarts. Elle **ne réécrit pas** le livrable à votre place — la relecture qualité est un contrôle, pas une correction automatique.

### 5.4 Mémo réglementaire

**À quoi ça sert.** Obtenir une note citée en réponse à une question réglementaire précise, directement rattachée à une mission comme livrable brouillon.

**Comment faire.**
1. Sur l'écran **Livrables**, repérez la section **Note de recherche (IA)**.
2. Sélectionnez la mission concernée, saisissez votre question, précisez si besoin le pôle et le titre du futur livrable.
3. Cliquez sur **Générer la note**.
4. La note apparaît avec ses sources citées et est ajoutée comme livrable brouillon de la mission.

**Ce que l'IA fait / ne fait pas.** Elle cite, elle ne tranche pas : la note expose ce que disent les textes, sans trancher une position à votre place. Elle s'abstient si le corpus ne couvre pas la question.

### 5.5 Saisie de temps assistée

**À quoi ça sert.** Transformer un récit libre de sa semaine en lignes de temps prêtes à valider, sans ressaisie manuelle fastidieuse.

**Comment faire.**
1. Sur l'écran **Feuilles de temps**, dans la section **Saisie assistée (IA)**, décrivez librement votre semaine (« lundi, 3h sur l'audit XYZ, rédaction du rapport… »).
2. Cliquez pour obtenir les suggestions.
3. Chaque ligne proposée (date, durée, mission, activité) peut être **ajustée puis ajoutée une par une**, ou écartée.

**Ce que l'IA fait / ne fait pas.** Elle propose des lignes plausibles à partir de votre texte. **Rien n'est créé dans votre feuille de temps sans un clic explicite de votre part** sur chaque ligne.

### 5.6 Alertes marge & sous-facturation

**À quoi ça sert.** Comprendre en un coup d'œil pourquoi certaines missions sont signalées en difficulté de rentabilité, et lesquelles traiter en priorité.

**Comment faire.**
1. Ouvrez **Alertes marge**. Le tableau des alertes (détection automatique, déterministe — pas de l'IA) liste les missions concernées avec sévérité, type d'alerte et impact chiffré.
2. Cliquez sur **Note de pilotage (IA)** pour obtenir une synthèse rédigée qui explique et priorise ces alertes.

**Ce que l'IA fait / ne fait pas.** La **détection** des alertes (marge négative, marge faible, sous-facturation) est un calcul déterministe du moteur, pas une supposition de l'IA. L'IA se contente de **narrer et prioriser** ce que le moteur a déjà détecté.

### 5.7 Synthèse d'entretien

**À quoi ça sert.** Transformer des notes brutes prises pendant un entretien, une réunion ou un atelier en compte rendu structuré, prêt à partager.

**Comment faire.**
1. Sur l'écran **Livrables**, dans la section **Synthèse d'entretien (IA)**, collez vos notes brutes.
2. Choisissez le type (entretien, réunion, atelier, appel) et, si besoin, un titre pour le futur livrable.
3. Cliquez sur **Générer le compte rendu**.
4. Le compte rendu (contexte, points clés, décisions, prochaines étapes) est ajouté comme livrable brouillon de la mission sélectionnée.

**Ce que l'IA fait / ne fait pas.** Elle met vos notes au propre **fidèlement, sans rien inventer** — elle structure ce que vous avez écrit, elle n'ajoute pas d'information qui n'y figurait pas.

---

## 6. Bonnes pratiques & FAQ

**L'assistant s'abstient sur ma question, que faire ?**
Ce n'est pas un bug : le corpus documentaire disponible ne couvre pas suffisamment votre question pour y répondre de façon fiable. Reformulez de façon plus précise, essayez depuis le module métier concerné (le pré-scopage aide le routage), ou signalez le manque à votre référent — le corpus peut être enrichi.

**L'assistant est « indisponible », que faire ?**
Le service d'IA est momentanément hors service (redémarrage, maintenance…). Réessayez dans quelques minutes. Si le problème persiste, contactez votre support IT interne.

**Dois-je toujours relire ce que l'IA propose ?**
Oui, systématiquement, avant de publier, envoyer ou valider quoi que ce soit. Un projet rédigé par l'IA — livrable, proposition, mémo, compte rendu, note de pilotage — reste un **brouillon à valider par un humain**, jamais un document final par défaut.

**Mes documents/mes données sont-ils en sécurité ?**
Oui. Toute l'IA de ZolaOS tourne en local, sans envoi vers un service cloud externe. Sur Zolabox, vos documents téléversés restent cloisonnés à votre organisation. Le cabinet Polaris (Zolacortex) n'a pas d'accès direct et permanent à vos données : tout accès s'inscrit dans le cadre strict, tracé et limité dans le temps d'une mission (principe Zero Trust).

**Qui voit quoi ?**
- Un utilisateur **client** (Zolabox) ne voit que les données de sa propre organisation.
- Un **consultant** (Zolacortex) voit les écrans de production de mission (pipeline, missions, temps, frais, livrables).
- Un **admin** (Zolacortex) voit en plus les écrans de pilotage et de gestion (plan de charge, honoraires, alertes marge, clients, comptes, facturation, journal d'audit).

**Puis-je faire confiance à un chiffre donné par l'IA (prix, marge, bulletin de paie…) ?**
Les montants ne sont jamais « inventés » par le modèle de langage : ils sont **calculés** par le moteur de règles métier (barèmes, formules déterministes) et l'IA se contente, quand elle intervient, de les expliquer ou de les mettre en récit.

---

## 7. Aide & support

- **Pour une question métier** (droit, comptabilité, RH…) : utilisez l'assistant intégré à ZolaOS — c'est sa raison d'être.
- **Pour un problème d'accès, de compte ou une panne technique** : contactez votre référent IT interne ou l'équipe support désignée par votre organisation. Ce guide ne couvre pas l'installation ni la configuration technique de la plateforme — ces aspects relèvent de la documentation technique dédiée.
- **Pour signaler un contenu incorrect ou une source manquante** : utilisez le retour utile/pas utile sous les réponses de l'assistant, ou remontez l'information à votre référent afin d'enrichir le corpus documentaire.

---

## 8. Glossaire

| Terme | Définition |
|---|---|
| **Mission** | Dossier de travail du cabinet pour un client donné (client, offre, périmètre, statut), point d'ancrage des feuilles de temps, livrables et honoraires. |
| **Livrable** | Document produit dans le cadre d'une mission (note, rapport, compte rendu…), suivant un cycle brouillon → en relecture → final. |
| **Encours / WIP** *(Work In Progress)* | Temps et frais déjà engagés sur une mission mais pas encore facturés au client. |
| **Ancrage** | Fait, pour une réponse de l'IA, de s'appuyer sur des documents identifiables du corpus (par opposition à une réponse générée « de mémoire » par le modèle). |
| **Abstention** | Choix délibéré de l'IA de ne pas répondre (ou de ne rien rédiger) faute de corpus suffisant, plutôt que de produire une réponse non vérifiable. |
| **Pôle / corpus** | Grand domaine métier (droit, ERP, santé, cyber, fintech…) auquel est rattaché un ensemble de documents de référence (le corpus) utilisé pour ancrer les réponses de l'assistant sur ce domaine. |
| **Zero Trust** | Principe selon lequel le cabinet (Zolacortex) n'a jamais d'accès direct et permanent aux données d'un client (Zolabox) ; tout accès est encadré, tracé et limité au périmètre et à la durée d'une mission. |
