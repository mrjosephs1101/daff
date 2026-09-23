import { handleUpload } from '@vercel/blob/client';

export default async function handler(request, response) {
  if (request.method !== 'POST') {
    return response.status(405).json({ error: 'method not allowed' });
  }

  try {
    const body = await request.json();

    const jsonResponse = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async (pathname, clientPayload, multipart) => {
        if (!pathname.toLowerCase().endsWith('.daff')) {
          throw new Error('only .daff files are allowed');
        }

        return {
          allowedContentTypes: ['application/octet-stream', 'application/x-daff'],
          maximumSizeInBytes: 5 * 1024 * 1024 * 1024,
          addRandomSuffix: true,
          tokenPayload: JSON.stringify({
            multipart: !!multipart,
            clientPayload: clientPayload || null,
          }),
        };
      },
      onUploadCompleted: async ({ blob, tokenPayload }) => {
        // Metadata is registered by the browser after upload() resolves.
        // This callback exists so Vercel Blob can acknowledge completion.
        console.log('DAFF Blob upload completed:', blob.pathname, tokenPayload);
      },
    });

    return response.status(200).json(jsonResponse);
  } catch (error) {
    return response.status(400).json({
      error: error instanceof Error ? error.message : String(error),
    });
  }
}
