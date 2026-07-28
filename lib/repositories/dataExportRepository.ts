import type { SupabaseClient } from "@supabase/supabase-js";
import type {
  DataExportCollections,
  DataExportRow,
} from "@/lib/services/dataExport";

type QueryResult = {
  data: unknown[] | null;
  error: unknown;
};

function unwrap(result: QueryResult, collection: string): DataExportRow[] {
  if (result.error) {
    // DB 오류 메시지에는 사용자 본문이 섞일 수 있어 컬렉션 이름만 남긴다.
    throw new Error(`data export query failed: ${collection}`);
  }
  return (result.data ?? []) as DataExportRow[];
}

function ids(rows: DataExportRow[], key = "id"): string[] {
  return rows
    .map((row) => row[key])
    .filter((value): value is string => typeof value === "string");
}

/** 세션 클라이언트의 RLS와 명시적 user/부모 id 필터를 함께 적용한다. */
export function createDataExportRepository(client: SupabaseClient) {
  async function children(
    table: string,
    columns: string,
    foreignKey: string,
    parentIds: string[],
    related?: { key: string; ids: string[] },
  ): Promise<DataExportRow[]> {
    if (parentIds.length === 0) return [];
    if (related && related.ids.length === 0) return [];
    let query = client
      .from(table)
      .select(columns)
      .in(foreignKey, parentIds);
    if (related) {
      query = query.in(related.key, related.ids);
    }
    const result = await query.order(foreignKey, { ascending: true });
    return unwrap(result, table);
  }

  return {
    async findAllByUserId(userId: string): Promise<DataExportCollections> {
      const [
        memoriesResult,
        entitiesResult,
        differencesResult,
        diariesResult,
        weeklyReportsResult,
      ] = await Promise.all([
        client
          .from("memories")
          .select(
            "id,user_id,captured_at,occurred_at,raw_text,source_type,memory_type,metadata,is_locked,deleted_at",
          )
          .eq("user_id", userId)
          .order("captured_at", { ascending: true }),
        client
          .from("entities")
          .select("id,user_id,entity_type,name,normalized_name")
          .eq("user_id", userId)
          .order("name", { ascending: true }),
        client
          .from("differences")
          .select(
            "id,user_id,date,entity_id,dimension,description,detection_method,confidence,status,category,evidence_state,staled_at",
          )
          .eq("user_id", userId)
          .order("date", { ascending: true }),
        client
          .from("diaries")
          .select(
            "id,user_id,date,status,style_profile,generated_text,edited_text,tone_instruction,regenerate_requested_at",
          )
          .eq("user_id", userId)
          .order("date", { ascending: true }),
        client
          .from("weekly_reports")
          .select("id,user_id,week")
          .eq("user_id", userId)
          .order("week", { ascending: true }),
      ]);

      const memories = unwrap(memoriesResult, "memories");
      const entities = unwrap(entitiesResult, "entities");
      const differences = unwrap(differencesResult, "differences");
      const diaries = unwrap(diariesResult, "diaries");
      const weeklyReports = unwrap(
        weeklyReportsResult,
        "weekly_reports",
      );

      const memoryIds = ids(memories);
      const entityIds = ids(entities);
      const differenceIds = ids(differences);
      const diaryIds = ids(diaries);
      const reportIds = ids(weeklyReports);

      const [
        differenceNarrations,
        emotions,
        assets,
        memoryEntities,
        differenceEvidence,
        diarySections,
        diarySources,
        weeklyReportHighlights,
      ] = await Promise.all([
        differenceIds.length === 0
          ? Promise.resolve([])
          : client
              .from("difference_narrations")
              .select(
                "id,user_id,difference_id,headline,body,evidence_text,model,created_at",
              )
              .eq("user_id", userId)
              .in("difference_id", differenceIds)
              .order("created_at", { ascending: true })
              .then((result) =>
                unwrap(result, "difference_narrations"),
              ),
        children(
          "emotions",
          "id,memory_id,valence,tags,confidence,confirmed_by_user",
          "memory_id",
          memoryIds,
        ),
        children(
          "assets",
          "id,memory_id,asset_type,file_url,mime_type",
          "memory_id",
          memoryIds,
        ),
        children(
          "memory_entities",
          "memory_id,entity_id,relation_type,confidence,confirmed_by_user",
          "memory_id",
          memoryIds,
          { key: "entity_id", ids: entityIds },
        ),
        children(
          "difference_evidence",
          "difference_id,memory_id",
          "difference_id",
          differenceIds,
          { key: "memory_id", ids: memoryIds },
        ),
        children(
          "diary_sections",
          "id,diary_id,difference_id,section_type,content",
          "diary_id",
          diaryIds,
        ),
        children(
          "diary_sources",
          "diary_id,memory_id",
          "diary_id",
          diaryIds,
          { key: "memory_id", ids: memoryIds },
        ),
        children(
          "weekly_report_highlights",
          "report_id,difference_id,slot,rank",
          "report_id",
          reportIds,
          { key: "difference_id", ids: differenceIds },
        ),
      ]);

      const ownedDifferenceIds = new Set(differenceIds);
      const safeDiarySections = diarySections.map((row) => {
        const differenceId = row.difference_id;
        if (
          typeof differenceId === "string" &&
          !ownedDifferenceIds.has(differenceId)
        ) {
          return { ...row, difference_id: null };
        }
        return row;
      });

      return {
        memories,
        emotions,
        assets,
        entities,
        memory_entities: memoryEntities,
        differences,
        difference_narrations: differenceNarrations,
        difference_evidence: differenceEvidence,
        diaries,
        diary_sections: safeDiarySections,
        diary_sources: diarySources,
        weekly_reports: weeklyReports,
        weekly_report_highlights: weeklyReportHighlights,
      };
    },
  };
}
