import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
export default defineConfig({root:path.resolve(import.meta.dirname),publicDir:'../public',plugins:[react()],resolve:{alias:{'@':path.resolve(import.meta.dirname,'..')}},build:{outDir:'../selfhost-dist',emptyOutDir:true}});
