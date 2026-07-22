# ============================================================================
# Packer — construit une image VM Zolabox (qcow2, convertible OVA) à partir d'une
# image cloud Ubuntu. L'image contient Docker + le bundle + le service systemd ;
# le client la démarre, renseigne son .env et lance ./install.sh.
#
# Prérequis (hôte de BUILD, Linux) : packer, qemu/kvm. Adapter iso_checksum et
# accelerator (kvm si dispo, sinon tcg — plus lent).
#   packer init . && packer build zolabox.pkr.hcl
# ============================================================================

packer {
  required_plugins {
    qemu = { version = ">= 1.1.0", source = "github.com/hashicorp/qemu" }
  }
}

variable "cloud_image_url" {
  default = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
}
variable "cloud_image_checksum" {
  default = "none" # ⚠️ remplacer par le sha256 réel de l'image en production
}
variable "disk_size"  { default = "20G" }
variable "output_dir" { default = "output-zolabox" }

source "qemu" "zolabox" {
  iso_url          = var.cloud_image_url
  iso_checksum     = var.cloud_image_checksum
  disk_image       = true
  disk_size        = var.disk_size
  format           = "qcow2"
  accelerator      = "kvm"
  headless         = true
  output_directory = var.output_dir
  vm_name          = "zolabox.qcow2"
  memory           = 2048
  cpus             = 2

  # Seed cloud-init pour ouvrir un accès SSH le temps du build (cf. seed/).
  cd_files = ["./seed/user-data", "./seed/meta-data"]
  cd_label = "cidata"

  ssh_username     = "builder"
  ssh_password     = "builder"
  ssh_timeout      = "15m"
  shutdown_command = "sudo shutdown -P now"
}

build {
  sources = ["source.qemu.zolabox"]

  provisioner "shell" {
    inline = [
      "cloud-init status --wait || true",
      "sudo apt-get update && sudo apt-get install -y git",
      "sudo git clone --depth 1 https://github.com/Mukatu/Zola_llm.git /opt/zolaos",
      "sudo sh /opt/zolaos/deploy/vm/provision.sh",
      # (Optionnel — image auto-portante hors-ligne : pré-construire l'image Docker
      #  et pré-télécharger le modèle 8B ici. Sinon install.sh le fait au 1er boot.)
      "sudo cloud-init clean --logs" # ré-arme cloud-init pour le premier boot client
    ]
  }

  post-processor "shell-local" {
    inline = [
      "echo 'Image qcow2 dans ${var.output_dir}/zolabox.qcow2'",
      "echo 'OVA/vmdk : qemu-img convert -O vmdk ${var.output_dir}/zolabox.qcow2 zolabox.vmdk, puis empaqueter en OVA.'"
    ]
  }
}
