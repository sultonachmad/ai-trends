"use client";

/** A receipt exactly as it was issued, ready to print. */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { PrintableBill } from "@/components/bills/PrintableBill";
import { fetchReceipt, type Receipt } from "@/lib/bills-api";
import { useLocale } from "@/lib/locale-store";

export default function ReceiptPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useLocale();
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchReceipt(id)
      .then((found) => {
        if (!cancelled) setReceipt(found);
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <p role="alert" className="p-8 text-sm">{t("common.loadFailed", { reason: error })}</p>;
  if (!receipt) return <p className="p-8 text-sm text-muted-foreground">{t("common.loading")}</p>;
  return (
    <PrintableBill
      heading={t("bills.receiptHeading")}
      number={receipt.number}
      issuedOn={receipt.business_date ?? receipt.issued_at.slice(0, 10)}
      issuer={receipt.issuer_name || receipt.property_name}
      taxId={receipt.issuer_tax_id}
      bookingNumber={receipt.booking_number}
      guestName={receipt.guest_name}
      arrival={receipt.arrival}
      departure={receipt.departure}
      paidToChannel={receipt.paid_to_channel}
      lines={receipt.lines.map((line) => ({
        description: line.description,
        quantity: line.quantity,
        amount: line.amount,
        isRoom: line.is_room,
      }))}
      total={receipt.total}
      paid={receipt.paid}
      balance={receipt.balance}
    />
  );
}
