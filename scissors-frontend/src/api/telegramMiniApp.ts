import axios from "axios";
import { API_BASE_URL } from "@/config/urls";

export interface MiniAppPhoto {
  id: number;
  url: string;
  caption: string;
  service_id?: number;
  service_title?: string;
}

export interface MiniAppProfile {
  name: string;
  price_level_display: string | null;
  bio: string;
  content: string;
  photo_url: string | null;
  services: { id: number; title: string }[];
  salons: { id: number; name: string }[];
  service_categories: { id: number; salon_id: number; title: string }[];
  assignments: {
    id: number;
    salon_id: number;
    service_id: number;
    title: string;
    category_id: number;
    category: string;
  }[];
  gallery: MiniAppPhoto[];
  works: MiniAppPhoto[];
}

export interface MiniAppServiceOption {
  id: number;
  title: string;
  category: string;
}

const miniAppApi = axios.create({ baseURL: API_BASE_URL });

function headers(initData: string) {
  return { Authorization: `tma ${initData}` };
}

export async function fetchMiniAppProfile(
  initData: string,
): Promise<MiniAppProfile> {
  const { data } = await miniAppApi.get<MiniAppProfile>("/staff/telegram/me/", {
    headers: headers(initData),
  });
  return data;
}

export async function saveMiniAppBio(
  initData: string,
  bio: string,
): Promise<void> {
  await miniAppApi.post(
    "/staff/telegram/bio/",
    { bio },
    { headers: headers(initData) },
  );
}

export async function saveMiniAppContent(
  initData: string,
  content: string,
): Promise<void> {
  await miniAppApi.post(
    "/staff/telegram/content/",
    { content },
    { headers: headers(initData) },
  );
}

export async function searchMiniAppServices(
  initData: string,
  salonId: number,
  categoryId: number,
  query: string,
): Promise<MiniAppServiceOption[]> {
  const { data } = await miniAppApi.get<{ results: MiniAppServiceOption[] }>(
    "/staff/telegram/services/",
    {
      params: { salon_id: salonId, category_id: categoryId, q: query },
      headers: headers(initData),
    },
  );
  return data.results;
}

export async function addMiniAppService(
  initData: string,
  salonId: number,
  serviceId: number,
): Promise<void> {
  await miniAppApi.post(
    "/staff/telegram/services/",
    { salon_id: salonId, service_id: serviceId },
    { headers: headers(initData) },
  );
}

export async function removeMiniAppService(
  initData: string,
  assignmentId: number,
): Promise<void> {
  await miniAppApi.delete(`/staff/telegram/services/${assignmentId}/`, {
    headers: headers(initData),
  });
}

export async function uploadMiniAppPhoto(
  initData: string,
  kind: "profile" | "gallery" | "work",
  file: File,
  serviceId?: number,
  caption = "",
): Promise<void> {
  const body = new FormData();
  body.append("kind", kind);
  body.append("image", file);
  if (serviceId !== undefined) body.append("service_id", String(serviceId));
  if (caption) body.append("caption", caption);
  await miniAppApi.post("/staff/telegram/photo/", body, {
    headers: headers(initData),
  });
}

export function miniAppError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (!error.response)
      return "Не удалось связаться с сервером API. Проверьте соединение и попробуйте ещё раз.";
    const data = error.response?.data as Record<string, unknown> | undefined;
    const detail = data?.detail;
    if (typeof detail === "string") return detail;
    const field =
      data && Object.values(data).find((value) => Array.isArray(value));
    if (Array.isArray(field) && typeof field[0] === "string") return field[0];
    return `Сервер вернул ошибку ${error.response.status}. Попробуйте ещё раз.`;
  }
  return "Не удалось выполнить запрос. Попробуйте ещё раз.";
}
