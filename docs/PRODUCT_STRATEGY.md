# Stratégie produit ZolaOS — « Un moteur, deux faces »

**Date** : 2026-06-21
**Objet** : réconcilier les deux ambitions — (1) un **orchestrateur IA** multi-agents qui rivalise avec les géants, et (2) un **SaaS** (système d'information moderne) qui se vend aux entreprises. Elles **ne s'opposent pas** : ce sont deux faces d'un même produit, livrées par **superposition**.

---

## 1. Le principe

```
FACE SaaS (ce qui se vend) :  Modules phares structurés  +  Assistant conversationnel universel
            │  consomment des CONTRATS typés (API /v1 + schémas d'entrée/sortie)
MOTEUR (ce qui fait la force) :  Orchestrateur + brigade d'agents + connecteurs + moteurs déterministes
```

- **Moteur** = le **fossé défensif** (souverain, local, multi-agents, tous métiers, extensible). Déjà construit.
- **Face SaaS** = la **surface commerciale** (modules reconnaissables, multi-tenant, personnalisable). Posée **par-dessus** le même moteur — jamais un produit parallèle.

## 2. Les deux faces, un seul moteur

| Face | Rôle | Pour qui | Ce qu'elle apporte |
|------|------|----------|--------------------|
| **Conversation** (Assistant) | porte d'entrée unique, l'orchestrateur route vers n'importe quel agent | tous, tout métier | **breadth** + extensibilité (rivalise avec les géants) |
| **Modules structurés phares** | workflows à forte valeur, saisie/données | métiers récurrents | **le produit qui se facture** (SaaS reconnaissable) |

Les deux **consomment les mêmes contrats** (un agent = un schéma d'entrée/sortie). Rien n'est dupliqué.

## 3. Chaque capacité a un écran — mais les écrans sont *générés*, pas dessinés un par un

**Toute capacité métier a son écran** (sinon elle est invisible = « n'existe pas » pour l'utilisateur). La discipline anti-dispersion ne consiste **pas** à supprimer des écrans, mais à **les générer depuis un cadre commun** :

- **Cadre d'écran de capacité** : chaque agent déclare son **schéma** (intents, entrée, sortie) ; l'UI **génère** un écran standard (formulaire d'entrée + rendu de sortie + repli conversationnel). → ajouter un pôle = un écran **automatiquement**, sans maquette neuve.
- **Phares (écran enrichi sur mesure)** seulement si : **fréquent + saisie/données fortes + facturable** (Paie, Compta, CRM, Pilotage/BI, Doc-gen).
- **Assistant** = entrée transverse complémentaire (orchestrateur) par-dessus tout.
- **Routage par audience** : `client` (Zolabox), `cabinet` (Zolacortex) ou `les deux`.
- **Sans écran = uniquement les méta-agents internes** (Router, Planning, Mémoire) — tuyauterie, pas métier.

**Conséquence** : GRC, Fintech, Cyber, Pôle K — **ont chacun leur écran** (généré), routé vers le bon public ; couverture 100 %, zéro dette de maquettes.

## 4. Application à ZolaOS

- **Chaque capacité = un écran** (cf. inventaire complet dans `docs/UX_DESIGN_SPEC.md`), routé par audience :
  - **Client (Zolabox)** : Santé, Droit (4 modules + à venir), **Code Agent**, ERP (RH/Paie/Finance/Compta/Projets ONG), BI, CRM, Marketing, GRC, Fintech, Cyber, Pôle K.
  - **Cabinet (Zolacortex)** : les 16 overlays d'audit (mission), dont **Code-Review** et **Audit-Sécurité-Code**.
  - **Les deux** : Code, Pilotage/BI, Assistant, Pôle K.
- **Phares (écran enrichi sur mesure)** : Paie, Comptabilité, CRM (pipeline), Pilotage/BI, Génération de documents.
- **Tous les autres** : écran **généré** par le cadre de capacité (formulaire + rendu de sortie) — pas de maquette manuelle.
- **Personnalisation** (`modules_actifs`) : décide **quelles capacités** un client voit ; l'Assistant est toujours présent.
- **Sans écran** : Router, Planning, Mémoire (méta-agents internes).

## 5. Angle commercial

- **Ce qui se vend** (face SaaS) : « votre système d'information augmenté par l'IA, souverain et local » — modules concrets, par métier, par client.
- **Le différenciateur/moat** (moteur) : multi-agents souverain, tous métiers, hors-ligne, données chez le client (Zero Trust Polaris). C'est ce que les géants **ne** font **pas** sur ce marché.
- Le mode **Polaris (Zolacortex)** vend le **conseil augmenté** par le même moteur.

## 6. Décision

On construit **les deux faces sur l'unique moteur** :
1. **Assistant conversationnel** (orchestrateur-natif) = socle universel.
2. **Modules phares structurés** = la couche SaaS qui se vend.
3. **Rendu générique par schéma** pour tout le reste (extensibilité).

→ `docs/UX_DESIGN_SPEC.md` sera révisé pour refléter ce modèle (et non « un écran par module »).

---

*Stratégie établie le 2026-06-21. Réconcilie orchestrateur (moat) et SaaS (vente) par superposition — pas un choix de l'un OU l'autre.*
