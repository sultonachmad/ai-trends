"use client";

/**
 * Generic, reusable data table for the crud-scaffold prefab.
 *
 * Renders any array of records against a `columns` config, with optional
 * client-side search and Edit/Delete action buttons. Column values are
 * `any` because the data shape is only known by the caller — narrow it in
 * a `render` function when a column needs typed formatting.
 */

import { useMemo, useState, type ReactNode } from "react";

export interface Column<T> {
  key: string;
  label: string;
  render?: (value: any, item: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  onEdit?: (item: T) => void;
  onDelete?: (item: T) => void;
  searchable?: boolean;
}

function rowKey<T>(item: T, index: number): string | number {
  const id = (item as { id?: string | number }).id;
  return id ?? index;
}

function matchesQuery<T>(item: T, columns: Column<T>[], needle: string): boolean {
  return columns.some((column) => {
    const value = (item as Record<string, unknown>)[column.key];
    if (value === null || value === undefined) {
      return false;
    }
    return String(value).toLowerCase().includes(needle);
  });
}

export function DataTable<T>({ columns, data, onEdit, onDelete, searchable = false }: DataTableProps<T>) {
  const [query, setQuery] = useState("");
  const showActions = Boolean(onEdit || onDelete);

  const filteredData = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!searchable || needle === "") {
      return data;
    }
    return data.filter((item) => matchesQuery(item, columns, needle));
  }, [data, columns, query, searchable]);

  return (
    <div className="space-y-4">
      {searchable && (
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search..."
          aria-label="Search"
          className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      )}

      <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider"
                >
                  {column.label}
                </th>
              ))}
              {showActions && (
                <th
                  scope="col"
                  className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider"
                >
                  Actions
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-gray-900">
            {filteredData.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (showActions ? 1 : 0)}
                  className="px-6 py-8 text-center text-sm text-gray-500 dark:text-gray-500"
                >
                  No records found.
                </td>
              </tr>
            ) : (
              filteredData.map((item, index) => (
                <tr key={rowKey(item, index)} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  {columns.map((column) => {
                    const value = (item as Record<string, unknown>)[column.key];
                    return (
                      <td
                        key={column.key}
                        className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100"
                      >
                        {column.render ? column.render(value, item) : String(value ?? "")}
                      </td>
                    );
                  })}
                  {showActions && (
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm space-x-2">
                      {onEdit && (
                        <button
                          type="button"
                          onClick={() => onEdit(item)}
                          className="inline-flex items-center px-3 py-1.5 rounded-md bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-600"
                        >
                          Edit
                        </button>
                      )}
                      {onDelete && (
                        <button
                          type="button"
                          onClick={() => onDelete(item)}
                          className="inline-flex items-center px-3 py-1.5 rounded-md bg-red-600 text-white text-xs font-medium hover:bg-red-700"
                        >
                          Delete
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
