"use client";

// Cockpit cabinet (Zolacortex) : GED — bibliothèque de modèles de livrables
// (admin:users) et livrables versionnés par mission (tout consultant).
import { useEffect, useState } from "react";
import { Files, FileText, Plus, Save, ScanSearch, Sparkles, Trash2, X } from "lucide-react";
import { Card, Button, Badge, Skeleton, type BadgeTone } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useZola, hasScope } from "@/components/ConfigProvider";
import { listMissions, type MissionSummary } from "@/lib/cortex";
import {
  listTemplates,
  createTemplate,
  updateTemplate,
  listDeliverables,
  getDeliverable,
  createDeliverable,
  updateDeliverable,
  draftDeliverable,
  reviewDeliverable,
  type Template,
  type Section,
  type DeliverableBrief,
  type Deliverable,
  type DeliverableStatus,
  type ReviewResult,
} from "@/lib/cortex-ged";

const STATUS_TONE: Record<DeliverableStatus, BadgeTone> = {
  draft: "grey",
  review: "amber",
  final: "green",
};

const STATUS_LABEL: Record<DeliverableStatus, string> = {
  draft: "brouillon",
  review: "en révision",
  final: "final",
};

const STATUSES: DeliverableStatus[] = ["draft", "review", "final"];

function messageFromError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  if (e.status === 403) return "Accès réservé aux administrateurs.";
  return fallback;
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", { year: "numeric", month: "short", day: "numeric" });
}

function emptySection(): Section {
  return { title: "", guidance: "" };
}

export default function LivrablesPage() {
  const { config, user } = useZola();
  const cabinetAllowed = hasScope(user, "admin:users");

  const [missions, setMissions] = useState<MissionSummary[]>([]);

  useEffect(() => {
    if (config.profil !== "cortex") return;
    listMissions()
      .then(setMissions)
      .catch(() => setMissions([]));
  }, [config.profil]);

  // --- Modèles de livrables (admin) ----------------------------------------
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [templatesErr, setTemplatesErr] = useState<string | null>(null);

  const [tplName, setTplName] = useState("");
  const [tplOffre, setTplOffre] = useState("");
  const [tplDescription, setTplDescription] = useState("");
  const [tplSections, setTplSections] = useState<Section[]>([emptySection()]);
  const [tplSaving, setTplSaving] = useState(false);
  const [tplErr, setTplErr] = useState<string | null>(null);
  const [busyTplId, setBusyTplId] = useState<string | null>(null);

  async function reloadTemplates() {
    setTemplatesLoading(true);
    try {
      const rows = await listTemplates({ active_only: false });
      setTemplates(rows);
      setTemplatesErr(null);
    } catch (e) {
      setTemplatesErr(messageFromError(e, "Bibliothèque de modèles indisponible."));
    } finally {
      setTemplatesLoading(false);
    }
  }

  useEffect(() => {
    if (!cabinetAllowed || config.profil !== "cortex") {
      setTemplatesLoading(false);
      return;
    }
    reloadTemplates();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cabinetAllowed, config.profil]);

  function addSection() {
    setTplSections((rows) => [...rows, emptySection()]);
  }

  function removeSection(index: number) {
    setTplSections((rows) => rows.filter((_, i) => i !== index));
  }

  function updateSection(index: number, field: keyof Section, value: string) {
    setTplSections((rows) => rows.map((s, i) => (i === index ? { ...s, [field]: value } : s)));
  }

  async function submitTemplate() {
    if (!tplName.trim()) {
      setTplErr("Nom requis.");
      return;
    }
    setTplSaving(true);
    setTplErr(null);
    try {
      await createTemplate({
        name: tplName.trim(),
        offre: tplOffre.trim() || null,
        description: tplDescription,
        sections: tplSections.filter((s) => s.title.trim().length > 0),
      });
      setTplName("");
      setTplOffre("");
      setTplDescription("");
      setTplSections([emptySection()]);
      await reloadTemplates();
    } catch (e) {
      setTplErr(messageFromError(e, "Échec de la création du modèle."));
    } finally {
      setTplSaving(false);
    }
  }

  async function toggleTemplateActive(tpl: Template) {
    setBusyTplId(tpl.id);
    try {
      await updateTemplate(tpl.id, { is_active: !tpl.is_active });
      await reloadTemplates();
    } catch (e) {
      setTemplatesErr(messageFromError(e, "Échec de la mise à jour du modèle."));
    } finally {
      setBusyTplId(null);
    }
  }

  // --- Livrables d'une mission ----------------------------------------------
  const [missionId, setMissionId] = useState("");
  const [deliverables, setDeliverables] = useState<DeliverableBrief[]>([]);
  const [deliverablesLoading, setDeliverablesLoading] = useState(false);
  const [deliverablesErr, setDeliverablesErr] = useState<string | null>(null);

  const [missionTemplates, setMissionTemplates] = useState<Template[]>([]);
  const [newTitle, setNewTitle] = useState("");
  const [newTemplateId, setNewTemplateId] = useState("");
  const [creatingDeliverable, setCreatingDeliverable] = useState(false);
  const [newErr, setNewErr] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Deliverable | null>(null);
  const [selectedLoading, setSelectedLoading] = useState(false);
  const [selectedErr, setSelectedErr] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [savingContent, setSavingContent] = useState(false);
  const [changingStatus, setChangingStatus] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [draftMsg, setDraftMsg] = useState<{ tone: "amber" | "success"; text: string } | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [reviewMsg, setReviewMsg] = useState<{ tone: "amber" | "success"; text: string } | null>(null);
  const [review, setReview] = useState<ReviewResult | null>(null);

  useEffect(() => {
    if (!missionId && missions.length > 0) setMissionId(missions[0].mission_id);
  }, [missions, missionId]);

  async function reloadDeliverables() {
    if (!missionId) return;
    setDeliverablesLoading(true);
    try {
      const rows = await listDeliverables({ mission_id: missionId });
      setDeliverables(rows);
      setDeliverablesErr(null);
    } catch (e) {
      setDeliverablesErr(messageFromError(e, "Livrables indisponibles (backend cortex requis)."));
    } finally {
      setDeliverablesLoading(false);
    }
  }

  useEffect(() => {
    if (!missionId) return;
    reloadDeliverables();
    setSelectedId(null);
    setSelected(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [missionId]);

  useEffect(() => {
    if (!missionId) {
      setMissionTemplates([]);
      return;
    }
    const mission = missions.find((m) => m.mission_id === missionId);
    listTemplates(mission?.offre ? { offre: mission.offre, active_only: true } : { active_only: true })
      .then(setMissionTemplates)
      .catch(() => setMissionTemplates([]));
  }, [missionId, missions]);

  async function submitDeliverable() {
    if (!missionId) {
      setNewErr("Sélectionnez une mission.");
      return;
    }
    if (!newTitle.trim()) {
      setNewErr("Titre requis.");
      return;
    }
    setCreatingDeliverable(true);
    setNewErr(null);
    try {
      await createDeliverable({
        mission_id: missionId,
        template_id: newTemplateId || null,
        title: newTitle.trim(),
      });
      setNewTitle("");
      setNewTemplateId("");
      await reloadDeliverables();
    } catch (e) {
      setNewErr(messageFromError(e, "Échec de la création du livrable."));
    } finally {
      setCreatingDeliverable(false);
    }
  }

  async function openDeliverable(id: string) {
    setSelectedId(id);
    setSelectedLoading(true);
    setSelectedErr(null);
    setDraftMsg(null);
    setReviewMsg(null);
    setReview(null);
    try {
      const d = await getDeliverable(id);
      setSelected(d);
      setEditContent(d.content);
    } catch (e) {
      setSelectedErr(messageFromError(e, "Livrable indisponible."));
    } finally {
      setSelectedLoading(false);
    }
  }

  async function saveContent() {
    if (!selected) return;
    setSavingContent(true);
    try {
      const d = await updateDeliverable(selected.id, { content: editContent });
      setSelected(d);
      setEditContent(d.content);
      await reloadDeliverables();
      setSelectedErr(null);
    } catch (e) {
      setSelectedErr(messageFromError(e, "Échec de l'enregistrement."));
    } finally {
      setSavingContent(false);
    }
  }

  async function changeStatus(newStatus: DeliverableStatus) {
    if (!selected) return;
    setChangingStatus(true);
    try {
      const d = await updateDeliverable(selected.id, { status: newStatus });
      setSelected(d);
      await reloadDeliverables();
      setSelectedErr(null);
    } catch (e) {
      setSelectedErr(messageFromError(e, "Échec du changement de statut."));
    } finally {
      setChangingStatus(false);
    }
  }

  async function draftWithAI() {
    if (!selected) return;
    setDrafting(true);
    setDraftMsg(null);
    try {
      const result = await draftDeliverable(selected.id, { apply: true });
      if (result.status === "generated") {
        const d = await getDeliverable(selected.id);
        setSelected(d);
        setEditContent(d.content);
        await reloadDeliverables();
        setDraftMsg({ tone: "success", text: "Projet généré et cité — à relire." });
      } else if (result.status === "abstained") {
        setDraftMsg({
          tone: "amber",
          text: "Le corpus ne couvre pas ce sujet — rien n'a été rédigé (aucune invention).",
        });
      } else {
        setDraftMsg({ tone: "amber", text: "Assistant IA momentanément indisponible." });
      }
    } catch (e) {
      setDraftMsg({ tone: "amber", text: messageFromError(e, "Assistant IA momentanément indisponible.") });
    } finally {
      setDrafting(false);
    }
  }

  async function reviewWithAI() {
    if (!selected) return;
    setReviewing(true);
    setReviewMsg(null);
    setReview(null);
    try {
      const result = await reviewDeliverable(selected.id, {});
      if (result.status === "generated") {
        setReview(result);
      } else if (result.status === "abstained") {
        setReviewMsg({
          tone: "amber",
          text: "Le corpus ne couvre pas ce sujet — pas de relecture possible.",
        });
      } else {
        setReviewMsg({ tone: "amber", text: "Assistant IA momentanément indisponible." });
      }
    } catch (e) {
      setReviewMsg({ tone: "amber", text: messageFromError(e, "Assistant IA momentanément indisponible.") });
    } finally {
      setReviewing(false);
    }
  }

  function closeReview() {
    setReview(null);
    setReviewMsg(null);
  }

  if (config.profil !== "cortex") {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <p className="text-sm text-muted">Réservé au cockpit cabinet.</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest">
          <Files className="h-5 w-5" />
        </span>
        <div>
          <h1 className="text-lg font-semibold">Livrables &amp; modèles</h1>
          <p className="text-sm text-muted">GED du cabinet — bibliothèque de modèles et documents de mission.</p>
        </div>
      </div>

      {/* --- Modèles de livrables (admin) --- */}
      {cabinetAllowed && (
        <Card className="flex flex-col gap-4">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <FileText className="h-4 w-4" /> Modèles de livrables
          </div>

          {templatesErr && <p className="text-sm text-amber-700">{templatesErr}</p>}
          {templatesLoading && !templates.length && (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          )}
          {!templatesLoading && templates.length === 0 && !templatesErr && (
            <p className="text-sm text-muted">Aucun modèle pour le moment.</p>
          )}
          {templates.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-black/5 text-left text-xs text-muted">
                    <th className="py-2 pr-3 font-medium">Nom</th>
                    <th className="py-2 pr-3 font-medium">Offre</th>
                    <th className="py-2 pr-3 font-medium">Sections</th>
                    <th className="py-2 pr-3 font-medium">Statut</th>
                    <th className="py-2 pr-3 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {templates.map((tpl) => (
                    <tr key={tpl.id} className="border-b border-black/5 last:border-0">
                      <td className="py-2 pr-3">{tpl.name}</td>
                      <td className="py-2 pr-3 text-muted">{tpl.offre ?? "—"}</td>
                      <td className="py-2 pr-3">{tpl.sections.length}</td>
                      <td className="py-2 pr-3">
                        <Badge tone={tpl.is_active ? "green" : "grey"}>
                          {tpl.is_active ? "actif" : "inactif"}
                        </Badge>
                      </td>
                      <td className="py-2 pr-3 text-right">
                        <Button
                          variant="ghost"
                          onClick={() => toggleTemplateActive(tpl)}
                          disabled={busyTplId === tpl.id}
                        >
                          {tpl.is_active ? "Désactiver" : "Activer"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="border-t border-black/5 pt-4">
            <div className="mb-3 text-sm font-semibold">Nouveau modèle</div>

            {tplErr && <p className="mb-2 text-sm text-amber-700">{tplErr}</p>}

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                <span className="mb-1 block font-medium">Nom</span>
                <input
                  type="text"
                  value={tplName}
                  onChange={(e) => setTplName(e.target.value)}
                  placeholder="ex. Rapport d'audit"
                  className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
                />
              </label>
              <label className="text-sm">
                <span className="mb-1 block font-medium">Offre (optionnel)</span>
                <input
                  type="text"
                  value={tplOffre}
                  onChange={(e) => setTplOffre(e.target.value)}
                  placeholder="ex. audit"
                  className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
                />
              </label>
            </div>

            <label className="mt-3 block text-sm">
              <span className="mb-1 block font-medium">Description</span>
              <input
                type="text"
                value={tplDescription}
                onChange={(e) => setTplDescription(e.target.value)}
                placeholder="ex. structure standard d'un rapport de mission"
                className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
              />
            </label>

            <div className="mt-3">
              <span className="mb-1 block text-sm font-medium">Sections</span>
              <div className="flex flex-col gap-2">
                {tplSections.map((section, index) => (
                  <div key={index} className="flex gap-2">
                    <input
                      type="text"
                      value={section.title}
                      onChange={(e) => updateSection(index, "title", e.target.value)}
                      placeholder="titre de la section"
                      className="w-1/3 rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
                    />
                    <input
                      type="text"
                      value={section.guidance}
                      onChange={(e) => updateSection(index, "guidance", e.target.value)}
                      placeholder="consigne de rédaction"
                      className="flex-1 rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
                    />
                    <Button variant="ghost" onClick={() => removeSection(index)} disabled={tplSections.length <= 1}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
              <div className="mt-2">
                <Button variant="ghost" onClick={addSection}>
                  <Plus className="h-3.5 w-3.5" /> Ajouter une section
                </Button>
              </div>
            </div>

            <div className="mt-3">
              <Button onClick={submitTemplate} disabled={tplSaving}>
                <Plus className="h-4 w-4" /> Créer le modèle
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* --- Livrables d'une mission --- */}
      <Card className="flex flex-col gap-4">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <FileText className="h-4 w-4" /> Livrables de mission
        </div>

        <label className="text-sm sm:max-w-xs">
          <span className="mb-1 block font-medium">Mission</span>
          {missions.length > 0 ? (
            <select
              value={missionId}
              onChange={(e) => setMissionId(e.target.value)}
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            >
              {missions.map((m) => (
                <option key={m.mission_id} value={m.mission_id}>
                  {m.offre}
                </option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              value={missionId}
              onChange={(e) => setMissionId(e.target.value)}
              placeholder="id de la mission"
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            />
          )}
        </label>

        {deliverablesErr && <p className="text-sm text-amber-700">{deliverablesErr}</p>}
        {deliverablesLoading && !deliverables.length && (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        )}
        {!deliverablesLoading && deliverables.length === 0 && !deliverablesErr && (
          <p className="text-sm text-muted">Aucun livrable pour cette mission.</p>
        )}
        {deliverables.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-black/5 text-left text-xs text-muted">
                  <th className="py-2 pr-3 font-medium">Titre</th>
                  <th className="py-2 pr-3 font-medium">Statut</th>
                  <th className="py-2 pr-3 font-medium">Version</th>
                  <th className="py-2 pr-3 font-medium">Mis à jour</th>
                </tr>
              </thead>
              <tbody>
                {deliverables.map((d) => (
                  <tr
                    key={d.id}
                    onClick={() => openDeliverable(d.id)}
                    className={
                      "cursor-pointer border-b border-black/5 last:border-0 hover:bg-black/[0.02] " +
                      (selectedId === d.id ? "bg-black/[0.03]" : "")
                    }
                  >
                    <td className="py-2 pr-3">{d.title}</td>
                    <td className="py-2 pr-3">
                      <Badge tone={STATUS_TONE[d.status]}>{STATUS_LABEL[d.status]}</Badge>
                    </td>
                    <td className="py-2 pr-3">v{d.version}</td>
                    <td className="py-2 pr-3 text-muted">{fmtDate(d.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="border-t border-black/5 pt-4">
          <div className="mb-3 text-sm font-semibold">Nouveau livrable</div>
          {newErr && <p className="mb-2 text-sm text-amber-700">{newErr}</p>}
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="text-sm sm:col-span-2">
              <span className="mb-1 block font-medium">Titre</span>
              <input
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="ex. Rapport final"
                className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block font-medium">Modèle (optionnel)</span>
              <select
                value={newTemplateId}
                onChange={(e) => setNewTemplateId(e.target.value)}
                className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
              >
                <option value="">Vierge</option>
                {missionTemplates.map((tpl) => (
                  <option key={tpl.id} value={tpl.id}>
                    {tpl.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="mt-3">
            <Button onClick={submitDeliverable} disabled={creatingDeliverable}>
              <Plus className="h-4 w-4" /> Nouveau livrable
            </Button>
          </div>
        </div>

        {selectedId && (
          <div className="border-t border-black/5 pt-4">
            {selectedErr && <p className="mb-2 text-sm text-amber-700">{selectedErr}</p>}
            {selectedLoading && !selected && (
              <div className="flex flex-col gap-2">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-40 w-full" />
              </div>
            )}
            {selected && (
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    {selected.title} <span className="text-xs font-normal text-muted">v{selected.version}</span>
                  </div>
                  <label className="flex items-center gap-2 text-sm">
                    <span className="font-medium">Statut</span>
                    <select
                      value={selected.status}
                      onChange={(e) => changeStatus(e.target.value as DeliverableStatus)}
                      disabled={changingStatus}
                      className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {STATUS_LABEL[s]}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  rows={16}
                  className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 font-mono text-xs"
                />

                {draftMsg && (
                  <p className={"text-sm " + (draftMsg.tone === "success" ? "text-forest" : "text-amber-700")}>
                    {draftMsg.text}
                  </p>
                )}

                <div className="flex flex-wrap items-center gap-3">
                  <Button onClick={saveContent} disabled={savingContent}>
                    <Save className="h-4 w-4" /> Enregistrer
                  </Button>
                  <Button variant="ghost" onClick={draftWithAI} disabled={drafting}>
                    <Sparkles className="h-4 w-4" /> {drafting ? "Rédaction en cours…" : "Générer un projet (IA)"}
                  </Button>
                  <Button variant="ghost" onClick={reviewWithAI} disabled={reviewing}>
                    <ScanSearch className="h-4 w-4" /> {reviewing ? "Relecture en cours…" : "Relire (IA)"}
                  </Button>
                </div>
                <p className="text-xs text-muted">
                  Projet ancré sur le corpus, cité, à relire (le moteur ne tranche pas).
                </p>

                {reviewMsg && (
                  <p className={"text-sm " + (reviewMsg.tone === "success" ? "text-forest" : "text-amber-700")}>
                    {reviewMsg.text}
                  </p>
                )}

                {review && (
                  <div className="rounded-xl border border-black/10 bg-black/[0.02] p-4">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <div className="text-sm font-semibold">Revue qualité (IA)</div>
                      <Button variant="ghost" onClick={closeReview}>
                        <X className="h-3.5 w-3.5" /> Fermer
                      </Button>
                    </div>
                    <p className="whitespace-pre-wrap text-sm">{review.review}</p>
                    <p className="mt-2 text-xs text-muted">
                      Contrôle contre le corpus — à valider par un consultant.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
