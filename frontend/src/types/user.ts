export interface User {
  user_id: string;
  display_name?: string | null;
  picture_url?: string | null;
  line_linked: boolean;
  notification_time?: string | null;
  timezone: string;
  created_at: string;
  updated_at?: string | null;
}

export interface UpdateUserRequest {
  display_name?: string;
  notification_time?: string;
}

export interface LinkLineRequest {
  line_user_id: string;
}
