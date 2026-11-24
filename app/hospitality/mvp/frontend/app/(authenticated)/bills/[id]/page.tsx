"use client";

/** The bill so far, printable before check-out. It is not a receipt. */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { PrintableBill } from "@/components/bills/PrintableBill";
import { fetchBill, type Bill } from "@/lib/bills-api";
import { fetchWorkspace } from "@/lib/workspace-api";
import { useLocale } from "@/lib/locale-store";

export default function BillPrintPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useLocale();
  const [bill, setBill] = useState<Bill | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [issuer, setIssuer] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchBill(id), fetchWorkspace()])
      .then(([found, workspace]) => {
        if (cancelled) return;
        setBill(found);
        setIssuer(workspace.property.name);
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <p role="alert" className="p-8 text-sm">{t("common.loadFailed", { reason: error })}</p>;
  if (!bill) return <p className="p-8 text-sm text-muted-foreground">{t("common.loading")}</p>;
  const owed = bill.paid_to_channel ? "0" : bill.room_total;
  const added = bill.taxes.included ? 0 : Number(bill.taxes.service) + Number(bill.taxes.pbjt);
  const total = String(Number(owed) + Number(bill.extras_total) + added);
  return (
    <PrintableBill
      heading={t("bills.billHeading")}
      number={null}
      issuedOn={null}
      issuer={issuer}
      taxId={null}
      bookingNumber={bill.number}
      guestName={bill.guest_name}
      arrival={bill.arrival}
      departure={bill.departure}
      paidToChannel={bill.paid_to_channel}
      lines={[
        {
          description: bill.room_type,
          quantity: String(bill.room_nights.length),
          amount: owed,
          isRoom: true,
        },
        ...bill.lines
          .filter((line) => !line.voided)
          .map((line) => ({
            description: line.description,
            quantity: line.quantity,
            amount: line.amount,
            isRoom: false,
          })),
      ]}
      taxes={bill.taxes.confirmed ? bill.taxes : null}
      total={total}
      paid={bill.paid}
      balance={bill.balance}
    />
  );
}
