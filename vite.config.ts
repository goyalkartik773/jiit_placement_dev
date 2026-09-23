import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The backend CORS policy (Program.cs) allows exactly:
//   http://localhost:3000 and http://localhost:5173
// So the dev server is pinned to 5173 to always match the allowed origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
  preview: {
    port: 5173,
    strictPort: true,
  },
});
