"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useSearch } from "@/hooks/useSearch";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Search, ArrowUpRight, RefreshCw } from "lucide-react";

export default function SearchDiscoveryPage() {
  const [searchInput, setSearchInput] = useState("");
  const [authorInput, setAuthorInput] = useState("");
  const [yearInput, setYearInput] = useState("");

  const {
    params,
    updateSearch,
    results,
    pagination,
    isLoading,
    isFetching,
  } = useSearch();

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    updateSearch({
      q: searchInput.trim() || undefined,
      author: authorInput.trim() || undefined,
      year: yearInput ? parseInt(yearInput, 10) : undefined,
      page: 1,
    });
  };

  const handleClear = () => {
    setSearchInput("");
    setAuthorInput("");
    setYearInput("");
    updateSearch({ q: undefined, author: undefined, year: undefined, page: 1 });
  };

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="border-b border-zinc-200/80 pb-4 dark:border-zinc-800 space-y-1">
        <div className="flex items-center gap-2">
          <Search className="h-5 w-5 text-zinc-900 dark:text-zinc-100" />
          <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
            Literature Search & Discovery
          </h1>
        </div>
        <p className="text-xs text-zinc-500 font-mono">
          Perform database metadata queries across paper titles, abstracts, authors, and publication years.
        </p>
      </div>

      {/* Search Input Bar & Facets */}
      <form
        onSubmit={handleSearchSubmit}
        className="rounded-xl border border-zinc-200 bg-white p-4 space-y-3 dark:border-zinc-800 dark:bg-zinc-900 shadow-2xs"
      >
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
            <Input
              placeholder="Search by keywords in title or abstract..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="pl-9 h-9 text-xs"
            />
          </div>

          <Button
            type="submit"
            variant="workbench"
            disabled={isFetching}
            className="h-10 px-4 text-sm gap-1.5 shrink-0"
          >
            {isFetching ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Search className="h-3.5 w-3.5" />
            )}
            <span>Search Database</span>
          </Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1 border-t border-zinc-100 dark:border-zinc-800">
          <div className="space-y-1">
            <label className="text-[10px] font-mono text-zinc-500 uppercase">
              Author Match
            </label>
            <Input
              placeholder="e.g. Vaswani, Hinton, LeCun"
              value={authorInput}
              onChange={(e) => setAuthorInput(e.target.value)}
              className="h-8 text-xs"
            />
          </div>

          <div className="flex items-end gap-2">
            <div className="space-y-1 flex-1">
              <label className="text-[10px] font-mono text-zinc-500 uppercase">
                Publication Year
              </label>
              <Input
                type="number"
                placeholder="2024"
                value={yearInput}
                onChange={(e) => setYearInput(e.target.value)}
                className="h-8 text-xs"
              />
            </div>

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleClear}
              className="h-8 text-xs text-zinc-500 hover:text-zinc-900"
            >
              Clear
            </Button>
          </div>
        </div>
      </form>

      {/* Results Header */}
      <div className="flex items-center justify-between text-xs font-mono text-zinc-500">
        <span>
          Found {pagination.total} matching paper(s)
          {params.q ? ` for "${params.q}"` : ""}
        </span>
      </div>

      {/* Results List */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 rounded-lg bg-zinc-100 animate-pulse" />
          ))}
        </div>
      ) : results.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-12 text-center dark:border-zinc-800 dark:bg-zinc-900 space-y-2">
          <Search className="mx-auto h-8 w-8 text-zinc-300 stroke-[1.5]" />
          <h3 className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
            No papers match your search
          </h3>
          <p className="text-[11px] text-zinc-400">
            Try broadening your search query or clear filters.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {results.map((paper) => (
            <Card
              key={paper.id}
              className="border-zinc-200 bg-white hover:border-zinc-300 transition-all dark:border-zinc-800 dark:bg-zinc-900 shadow-2xs"
            >
              <CardContent className="p-4 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1 min-w-0">
                    <Link
                      href={`/papers/${paper.id}`}
                      className="text-sm font-semibold text-zinc-900 hover:text-blue-600 dark:text-zinc-100 line-clamp-1"
                    >
                      {paper.title}
                    </Link>

                    <div className="flex items-center gap-2 text-xs text-zinc-500">
                      <span>{paper.authors?.join(", ") || "Unknown authors"}</span>
                      {paper.publication_year && <span>• {paper.publication_year}</span>}
                      {paper.venue && <span>• {paper.venue}</span>}
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    <Button variant="outline" size="sm" asChild className="h-7 text-xs">
                      <Link href={`/papers/${paper.id}`}>
                        <span>Inspect</span>
                        <ArrowUpRight className="ml-1 h-3 w-3" />
                      </Link>
                    </Button>
                  </div>
                </div>

                {paper.abstract && (
                  <p className="text-xs text-zinc-600 line-clamp-2 leading-relaxed dark:text-zinc-400">
                    {paper.abstract}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
