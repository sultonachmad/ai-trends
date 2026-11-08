"use client";

/**
 * Generic, data-driven form for the crud-scaffold prefab.
 *
 * Renders one input per entry in `fields`, keeps form state in a
 * `useReducer` (every update produces a new state object rather than
 * mutating the previous one), and calls `onSubmit` with the collected
 * values on submit.
 */

import { useReducer, type FormEvent } from "react";

export interface SelectOption {
  value: string;
  label: string;
}

export interface FieldConfig {
  name: string;
  label: string;
  type: "text" | "email" | "number" | "date" | "select" | "textarea" | "checkbox";
  required?: boolean;
  options?: SelectOption[];
  placeholder?: string;
}

interface EntityFormProps {
  fields: FieldConfig[];
  onSubmit: (data: Record<string, any>) => void | Promise<void>;
  initialData?: Record<string, any>;
  submitLabel?: string;
}

interface FormState {
  values: Record<string, any>;
  submitting: boolean;
  error: string | null;
}

type FormAction =
  | { type: "SET_FIELD"; name: string; value: any }
  | { type: "SUBMIT_START" }
  | { type: "SUBMIT_SETTLED"; error: string | null };

function defaultValueFor(field: FieldConfig): any {
  return field.type === "checkbox" ? false : "";
}

function buildInitialValues(fields: FieldConfig[], initialData?: Record<string, any>): Record<string, any> {
  return fields.reduce<Record<string, any>>((values, field) => {
    const existing = initialData?.[field.name];
    return {
      ...values,
      [field.name]: existing !== undefined ? existing : defaultValueFor(field),
    };
  }, {});
}

function formReducer(state: FormState, action: FormAction): FormState {
  switch (action.type) {
    case "SET_FIELD":
      return {
        ...state,
        values: { ...state.values, [action.name]: action.value },
        error: null,
      };
    case "SUBMIT_START":
      return { ...state, submitting: true, error: null };
    case "SUBMIT_SETTLED":
      return { ...state, submitting: false, error: action.error };
    default:
      return state;
  }
}

const inputClass =
  "w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

interface FieldControlProps {
  field: FieldConfig;
  value: any;
  onChange: (value: any) => void;
}

function FieldControl({ field, value, onChange }: FieldControlProps) {
  if (field.type === "textarea") {
    return (
      <textarea
        id={field.name}
        name={field.name}
        required={field.required}
        placeholder={field.placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`${inputClass} min-h-[100px]`}
      />
    );
  }

  if (field.type === "select") {
    return (
      <select
        id={field.name}
        name={field.name}
        required={field.required}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={inputClass}
      >
        <option value="" disabled>
          {field.placeholder ?? "Select..."}
        </option>
        {(field.options ?? []).map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }

  if (field.type === "checkbox") {
    return (
      <input
        id={field.name}
        name={field.name}
        type="checkbox"
        checked={Boolean(value)}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
      />
    );
  }

  return (
    <input
      id={field.name}
      name={field.name}
      type={field.type}
      required={field.required}
      placeholder={field.placeholder}
      value={value}
      onChange={(event) =>
        onChange(field.type === "number" ? event.target.valueAsNumber : event.target.value)
      }
      className={inputClass}
    />
  );
}

export function EntityForm({ fields, onSubmit, initialData, submitLabel = "Save" }: EntityFormProps) {
  const [state, dispatch] = useReducer(formReducer, undefined, () => ({
    values: buildInitialValues(fields, initialData),
    submitting: false,
    error: null,
  }));

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    dispatch({ type: "SUBMIT_START" });
    try {
      await onSubmit(state.values);
      dispatch({ type: "SUBMIT_SETTLED", error: null });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to submit form.";
      dispatch({ type: "SUBMIT_SETTLED", error: message });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {fields.map((field) => (
        <div key={field.name}>
          <label
            htmlFor={field.name}
            className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
          >
            {field.label}
            {field.required && <span className="text-red-600"> *</span>}
          </label>
          <FieldControl
            field={field}
            value={state.values[field.name]}
            onChange={(value) => dispatch({ type: "SET_FIELD", name: field.name, value })}
          />
        </div>
      ))}

      {state.error && <p className="text-sm text-red-600 dark:text-red-400">{state.error}</p>}

      <button
        type="submit"
        disabled={state.submitting}
        className="inline-flex items-center px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {state.submitting ? "Saving..." : submitLabel}
      </button>
    </form>
  );
}
