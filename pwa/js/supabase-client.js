
// Initialize Supabase
const SUPABASE_URL = 'https://jgutioxkysbudlazuyhs.supabase.co';
const SUPABASE_KEY = 'sb_publishable_bAGQwQopWHk2rNvW29luFw_2lJcErzQ'; // In prod, use environment variables or proxy, but acceptable for MVP prototype

const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

// Auth Helpers
export async function signInWithStrava() {
    // Note: To use Strava, we need to configure it in Supabase Auth providers.
    // For now, let's just do a simple email/password demo OR anonymous login if allowed.
    // Or we can just use 'signInAnonymously' if enabled? 
    // Let's assume we want to use Google/Github or just Email for testing phase.

    // For MVP quick test:
    const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google', // Requires Config
        options: {
            redirectTo: window.location.origin + '/pwa/'
        }
    });
    return { data, error };
}

export async function getCurrentUser() {
    const { data: { user } } = await supabase.auth.getUser();
    return user;
}

// Upload Helper
export async function uploadRun(videoBlob, analysisJson, metadata) {
    const user = await getCurrentUser();
    if (!user) throw new Error("User not logged in");

    const timestamp = Date.now();
    const fileName = `${user.id}/${timestamp}_run.webm`;

    // 1. Upload Video
    const { data: uploadData, error: uploadError } = await supabase.storage
        .from('videos')
        .upload(fileName, videoBlob);

    if (uploadError) throw uploadError;

    const videoUrl = uploadData.path; // or getPublicUrl

    // 2. Insert Activity Record
    const { data: insertData, error: insertError } = await supabase
        .from('activities')
        .insert({
            user_id: user.id,
            video_url: videoUrl,
            ai_analysis_json: analysisJson,
            date: new Date().toISOString(),
            status: 'pending',
            distance_meters: metadata.distance || 0,
            duration_seconds: metadata.duration || 0
        })
        .select()
        .single();

    if (insertError) throw insertError;

    return insertData;
}
