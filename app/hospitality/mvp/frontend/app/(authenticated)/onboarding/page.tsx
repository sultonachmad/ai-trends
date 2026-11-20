"use client";

/**
 * Onboarding — a signed-in account with no workspace names its property here.
 * Reachable at `/onboarding`; an account that already has a workspace is sent on
 * to `/dashboard`.
 */

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { EntityForm, type FieldConfig } from "@/components/EntityForm";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { ONBOARDING_PROPERTY_TYPES } from "@/lib/i18n";
import { useLocale } from "@/lib/locale-store";
import { createWorkspace, fetchOnboardingStatus } from "@/lib/workspace-api";

const WORKSPACE_HOME = "/dashboard";
const MIN_NAME_LENGTH = 2;

type CheckState = "checking" | "needed" | "failed";

export default function OnboardingPage() {
  const router = useRouter();
  const { t } = useLocale();
  const [check, setCheck] = useState<CheckState>("checking");
  const [checkError, setCheckError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchOnboardingStatus()
      .then((status) => {
        if (cancelled) return;
        if (status.has_workspace) {
          router.replace(WORKSPACE_HOME);
        } else {
          setCheck("needed");
        }
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setCheckError(error instanceof Error ? error.message : String(error));
        setCheck("failed");
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  const fields = useMemo<FieldConfig[]>(
    () => [
      {
        name: "property_name",
        label: t("onboarding.propertyName"),
        type: "text",
        required: true,
        placeholder: t("onboarding.propertyNamePlaceholder"),
      },
      {
        name: "property_type",
        label: t("onboarding.propertyType"),
        type: "select",
        required: true,
        options: ONBOARDING_PROPERTY_TYPES.map((value) => ({
          value,
          label: t(`propertyType.${value}`),
        })),
      },
      {
        name: "city",
        label: t("onboarding.city"),
        type: "text",
        required: true,
        placeholder: t("onboarding.cityPlaceholder"),
      },
    ],
    [t],
  );

  const handleSubmit = async (values: Record<string, unknown>) => {
    const propertyName = String(values.property_name ?? "").trim();
    const city = String(values.city ?? "").trim();
    if (propertyName.length < MIN_NAME_LENGTH) {
      throw new Error(t("onboarding.nameTooShort"));
    }
    if (city.length === 0) {
      throw new Error(t("onboarding.cityRequired"));
    }
    await createWorkspace({
      property_name: propertyName,
      property_type: String(values.property_type ?? ""),
      city,
    });
    router.replace(WORKSPACE_HOME);
  };

  if (check === "checking") {
    return <p className="p-8 text-sm text-muted-foreground">{t("common.loading")}</p>;
  }

  if (check === "failed") {
    return (
      <p role="alert" className="p-8 text-sm text-destructive">
        {t("common.loadFailed", { reason: checkError })}
      </p>
    );
  }

  return (
    <div className="mx-auto max-w-md space-y-6 py-8">
      <div className="flex justify-end">
        <LanguageSwitch />
      </div>
      <div className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm">
        <h1 className="text-2xl font-bold">{t("onboarding.title")}</h1>
        <p className="mb-6 mt-1 text-sm text-muted-foreground">{t("onboarding.subtitle")}</p>
        <EntityForm
          fields={fields}
          onSubmit={handleSubmit}
          initialData={{ property_type: ONBOARDING_PROPERTY_TYPES[0] }}
          submitLabel={t("onboarding.submit")}
        />
      </div>
    </div>
  );
}
