export interface User {
  user_id: string;
  email: string;
  display_name: string;
  line_user_id?: string;
  notification_time?: string;
  created_at: string;
  updated_at: string;
}

export interface UpdateUserRequest {
  display_name?: string;
  notification_time?: string;
}

export interface LinkLineRequest {
  line_user_id: string;
}
