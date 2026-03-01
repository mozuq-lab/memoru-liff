export interface User {
  user_id: string;
  display_name?: string | null;
  picture_url?: string | null;
  line_linked: boolean;
  notification_time?: string | null;
  timezone: string;
  day_start_hour: number;
  created_at: string;
  updated_at?: string | null;
}

export interface UpdateUserRequest {
  display_name?: string;
  notification_time?: string;
  day_start_hour?: number;
}

export interface LinkLineRequest {
  id_token: string;
}
