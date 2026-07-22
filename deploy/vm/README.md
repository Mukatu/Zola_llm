# Image VM Zolabox (clé-en-main)

Pour les clients qui veulent une **appliance à importer** (VMware/Proxmox/VirtualBox)
plutôt qu'un bundle Docker à installer. L'image contient déjà Docker + le bundle
Zolabox + un service systemd ; il ne reste au client qu'à renseigner l'identité de
sa box et lancer l'installation.

Deux voies — même logique de provisioning (`provision.sh`) :

## Voie A — cloud-init (le plus simple, si l'hyperviseur le supporte)

Proxmox, OpenStack, la plupart des clouds. Fournir `cloud-init/user-data` comme
user-data d'une image **Ubuntu 22.04+**. Au premier boot, la VM installe Docker,
clone le bundle et arme le service. Ensuite :

```sh
cd /opt/zolaos/deploy/zolabox
cp .env.zolabox.example .env    # identité de la box (provisioning Cortex)
./install.sh admin@le-client.cg
./seed_corpus.sh corpus_public.dump
```

## Voie B — Packer (OVA/qcow2 auto-portant)

Pour livrer un **fichier image** à importer. **Sur un hôte de build Linux** avec
`packer` + `qemu/kvm` :

```sh
cd deploy/vm
packer init .
packer build zolabox.pkr.hcl        # → output-zolabox/zolabox.qcow2
# OVA : qemu-img convert -O vmdk output-zolabox/zolabox.qcow2 zolabox.vmdk  puis empaqueter.
```

Détails :
- `provision.sh` : logique partagée (Docker + bundle `/opt/zolaos` + service `zolabox`).
- `zolabox.service` : remonte la pile au démarrage **une fois `.env` renseigné** (sinon inerte).
- `seed/` : cloud-init du **build** (utilisateur SSH temporaire ; nettoyé en fin de build).
- Avant un build de prod : renseigner `cloud_image_checksum` (sha256 de l'image Ubuntu),
  choisir `accelerator` (`kvm` si dispo, sinon `tcg`).

## Option : image entièrement hors-ligne

Par défaut, le **modèle 8B** et l'**image Docker** sont téléchargés/bâtis au premier
`install.sh` (réseau requis une fois). Pour une image totalement auto-portante,
pré-construire l'image Docker et `ollama pull` le modèle **pendant le build Packer**
(voir le commentaire dans `zolabox.pkr.hcl`) — l'OVA sera plus lourde mais installable
sans réseau.

## Statut

Recette **écrite, non construite ici** (le build OVA exige un hôte Linux + Packer/qemu).
La logique de provisioning (`provision.sh`) est la même que le bundle Compose, déjà
validé. À produire et tester lors de la phase pilote / sur une machine de build Polaris.
