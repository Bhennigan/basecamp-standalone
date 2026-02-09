import axios from "axios"

export const client = axios.create({
  baseURL: "",
  headers: {
    "Content-Type": "application/json",
    "X-Workspace-ID": "00000000-0000-0000-0000-000000000000",
  },
})
