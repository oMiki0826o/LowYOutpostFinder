/*
 * File: outpost_scan.c
 * Modification: 2026-10-12 — MC Java 1.21.8 low-Y outpost *candidate* finder.
 *
 * Reuses the user-provided LowYSwampHut C core only for worldgen sampling.
 * Reports projected WORLD_SURFACE_WG heights, NOT measured watchtower floor heights.
 * The search is a candidate screen; actual structure needs vanilla verification.
 */
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#  define WIN32_LEAN_AND_MEAN
#  include <windows.h>
#else
#  include <pthread.h>
#  include <unistd.h>
#endif

#include "rng.h"
#include "structure.h"
#include "phase2.h"
#include "biome.h"
#include "column_top.h"

enum { OUTPOST_SPACING=32, OUTPOST_SEPARATION=8, OUTPOST_SALT=165745296,
       VILLAGE_SPACING=34, VILLAGE_SEPARATION=8, VILLAGE_SALT=10387312 };

typedef struct { int cx, cz, x, z, y, max_surface_y, biome, sample_x, sample_z, rotation; } Hit;
typedef struct { uint64_t seed; int radius,max_y,limit,threads,large_biomes,candidates_only,skip_biome,template_width,template_depth,tower_center_offset_y,json,slice,strict_nearest; int x_min,x_max,z_min,z_max,center_x,center_z; int64_t start,count,start_ring,ring_count; const char *csv; } Opts;

/* ── Integer, RNG and vanilla placement ── */
static int floor_div(int a,int b) { int q=a/b,r=a%b;return q-(r<0); }
static int64_t parse_long(const char *s,const char *name) {
    errno=0;char *end=NULL;intmax_t v=strtoimax(s,&end,10);
    if(errno || !end || end==s || *end || v < INT64_MIN || v > INT64_MAX) {
        fprintf(stderr,"Invalid %s: %s\n",name,s);exit(2);
    }return (int64_t)v;
}
static int parse_int(const char *s,const char *name,int lo,int hi) {
    int64_t v=parse_long(s,name); if(v<lo||v>hi){fprintf(stderr,"%s outside [%d,%d]\n",name,lo,hi);exit(2);}return (int)v;
}
static lysh_chunkpos region_candidate(uint64_t seed,int rx,int rz,int spacing,int sep,int salt) {
    lysh_lcg rng; lysh_set_region_seed(&rng,seed,rx,rz,salt);
    int width=spacing-sep;
    lysh_chunkpos p={rx*spacing+lysh_lcg_next_int_bound(&rng,width),0};
    p.chunkZ=rz*spacing+lysh_lcg_next_int_bound(&rng,width);
    return p;
}
/* ── Vanilla legacy 1-in-5 frequency gate ── */
static int legacy_frequency(uint64_t seed,int cx,int cz) {
    uint32_t xi=(uint32_t)(cx>>4),zi=(uint32_t)(cz>>4);
    int32_t mix=(int32_t)(xi^(zi<<4));
    lysh_lcg r; lysh_lcg_set_seed(&r,seed^(uint64_t)(int64_t)mix);
    (void)lysh_lcg_next_bits(&r,32);
    return lysh_lcg_next_int_bound(&r,5)==0;
}
static int near_village_candidate(uint64_t seed,int cx,int cz) {
    int rx0=floor_div(cx-10,VILLAGE_SPACING),rx1=floor_div(cx+10,VILLAGE_SPACING);
    int rz0=floor_div(cz-10,VILLAGE_SPACING),rz1=floor_div(cz+10,VILLAGE_SPACING);
    for(int rz=rz0;rz<=rz1;rz++)for(int rx=rx0;rx<=rx1;rx++){
        lysh_chunkpos p=region_candidate(seed,rx,rz,VILLAGE_SPACING,VILLAGE_SEPARATION,VILLAGE_SALT);
        if(abs(p.chunkX-cx)<=10&&abs(p.chunkZ-cz)<=10)return 1;
    }return 0;
}

/* ── Biome whitelist (cubiomes IDs, vanilla 1.21.8 tag) ──
 * Source: data/minecraft/tags/worldgen/biome/has_structure/pillager_outpost.json
 * from the official 1.21.8 server JAR.  The tag contains desert, plains,
 * savanna, snowy_plains, taiga, grove, and #minecraft:is_mountain; the latter
 * expands to meadow, frozen/jagged/stony_peaks, snowy_slopes, cherry_grove. */
static int outpost_biome(int id) {
    switch(id) {
        case 1: /* plains */ case 2: /* desert */ case 5: /* taiga */
        case 12: /* snowy_plains */ case 35: /* savanna */
        case 177: /* meadow */ case 178: /* grove */ case 179: /* snowy_slopes */
        case 180: /* jagged_peaks */ case 181: /* frozen_peaks */
        case 182: /* stony_peaks */ case 185: /* cherry_grove */ return 1;
        default:return 0;
    }
}
/* ── Exact start-piece rotation and rotated bounding-box center ──
 * Structure.Context seeds a CheckedRandom via setCarverSeed, then Jigsaw
 * selects BlockRotation.random. This geometry is exact, not the terrain model.
 */
static int trunc_avg(int a, int b) { return (a + b) / 2; }
static void start_projection(uint64_t seed,int cx,int cz,int width,int depth,
                             int *sample_x,int *sample_z,int *rotation) {
    lysh_lcg r;lysh_lcg_set_seed(&r,seed);
    uint64_t a=lysh_lcg_next_long(&r),b=lysh_lcg_next_long(&r);
    uint64_t carver=(uint64_t)(int64_t)cx*a^(uint64_t)(int64_t)cz*b^seed;
    lysh_lcg_set_seed(&r,carver);
    int rot=lysh_lcg_next_int_bound(&r,4);
    int dx=width-1,dz=depth-1;
    if(rot==1){int t=dx;dx=-dz;dz=t;}
    else if(rot==2){dx=-dx;dz=-dz;}
    else if(rot==3){int t=dx;dx=dz;dz=-t;}
    int x=cx*16,z=cz*16;
    *rotation=rot;*sample_x=trunc_avg(x,x+dx);*sample_z=trunc_avg(z,z+dz);
}
static int terrain_top(void *user,int x,int z) {
    return lysh_phase2_height_pre_carver((lysh_phase2 *)user,x,z);
}
static int aquifer_column_top(void *user,int x,int z) {
    return lysh_preliminary_surface_level((const lysh_terrain *)user,x,z);
}

/* ── Result ordering and I/O ── */
static int hitcmp(const void *aa,const void *bb) {
    const Hit *a=(const Hit*)aa,*b=(const Hit*)bb;
    if(a->y!=b->y)return a->y<b->y?-1:1;
    if(a->x!=b->x)return a->x<b->x?-1:1;
    return a->z<b->z?-1:a->z>b->z?1:0;
}
static int hitcmp_nearest(const Hit *a,const Hit *b,int center_x,int center_z) {
    int64_t ax=(int64_t)a->cx*16-center_x, az=(int64_t)a->cz*16-center_z;
    int64_t bx=(int64_t)b->cx*16-center_x, bz=(int64_t)b->cz*16-center_z;
    int64_t ad=ax*ax+az*az, bd=bx*bx+bz*bz;
    if(ad!=bd)return ad<bd?-1:1;
    if(a->cx!=b->cx)return a->cx<b->cx?-1:1;
    return a->cz<b->cz?-1:a->cz>b->cz?1:0;
}
static void keep_nearest(Hit *hits,int *kept,int limit,const Hit *hit,int center_x,int center_z) {
    if(*kept<limit){hits[(*kept)++]=*hit;return;}
    int worst=0;
    for(int i=1;i<*kept;i++)if(hitcmp_nearest(&hits[i],&hits[worst],center_x,center_z)>0)worst=i;
    if(hitcmp_nearest(hit,&hits[worst],center_x,center_z)<0)hits[worst]=*hit;
}
static int cpu_count(void) {
#if defined(_WIN32)
    SYSTEM_INFO info;GetSystemInfo(&info);return info.dwNumberOfProcessors>0?(int)info.dwNumberOfProcessors:1;
#else
    long n=sysconf(_SC_NPROCESSORS_ONLN);return n>0?(int)n:1;
#endif
}
static void usage(const char *name) {
    printf("Usage: %s --seed SIGNED_LONG [--radius BLOCKS] [--max-y Y] [--top N] [--csv FILE] [--candidates-only] [--skip-biome] [--large-biomes] [--template-width N --template-depth N]\n",name);
    puts("Defaults: radius=8192 blocks, max-y=64, top=25, version=1.21.8 approximate noise.");
    puts("With a template: --max-y applies to projected BASEPLATE Y (surface - ground-level delta=1).");
    puts("Without a template: --max-y filters the approximate surface Y only.");
    puts("Output is NOT a verified tower Y, nor a confirmed structure in an ungenerated vanilla world.");
}
static Opts options(int argc,char **argv) {
    Opts o={.radius=8192,.max_y=64,.limit=25,.tower_center_offset_y=14};int have_seed=0;
    for(int i=1;i<argc;i++) {
        const char *a=argv[i];
        if(!strcmp(a,"--help")||!strcmp(a,"-h")){usage(argv[0]);exit(0);}
        if(!strcmp(a,"--candidates-only")){o.candidates_only=1;continue;}
        if(!strcmp(a,"--skip-biome")){o.skip_biome=1;continue;}
        if(!strcmp(a,"--large-biomes")){o.large_biomes=1;continue;}
        if(!strcmp(a,"--json")){o.json=1;continue;}
        if(i+1>=argc){fprintf(stderr,"Missing value for %s\n",a);exit(2);}const char *v=argv[++i];
        if(!strcmp(a,"--seed")){o.seed=(uint64_t)parse_long(v,"seed");have_seed=1;}
        else if(!strcmp(a,"--radius"))o.radius=parse_int(v,"radius",0,30000000);
        else if(!strcmp(a,"--max-y"))o.max_y=parse_int(v,"max-y",-64,320);
        else if(!strcmp(a,"--top"))o.limit=parse_int(v,"top",1,100000);
        else if(!strcmp(a,"--threads"))o.threads=parse_int(v,"threads",0,256);
        else if(!strcmp(a,"--template-width"))o.template_width=parse_int(v,"template-width",1,128);
        else if(!strcmp(a,"--template-depth"))o.template_depth=parse_int(v,"template-depth",1,128);
        else if(!strcmp(a,"--tower-center-offset-y"))o.tower_center_offset_y=parse_int(v,"tower-center-offset-y",0,128);
        else if(!strcmp(a,"--csv"))o.csv=v;
        else if(!strcmp(a,"--center-x"))o.center_x=parse_int(v,"center-x",-29999984,29999984);
        else if(!strcmp(a,"--center-z"))o.center_z=parse_int(v,"center-z",-29999984,29999984);
        else if(!strcmp(a,"--start-ring")){o.start_ring=parse_long(v,"start-ring");o.strict_nearest=1;}
        else if(!strcmp(a,"--ring-count")){o.ring_count=parse_long(v,"ring-count");o.strict_nearest=1;}
        else if(!strcmp(a,"--start")){o.start=parse_long(v,"start");o.slice=1;}
        else if(!strcmp(a,"--count")){o.count=parse_long(v,"count");o.slice=1;}
        else if(!strcmp(a,"--x-min")){o.x_min=parse_int(v,"x-min",-29999984,29999984);o.slice=1;}
        else if(!strcmp(a,"--x-max")){o.x_max=parse_int(v,"x-max",-29999984,29999984);o.slice=1;}
        else if(!strcmp(a,"--z-min")){o.z_min=parse_int(v,"z-min",-29999984,29999984);o.slice=1;}
        else if(!strcmp(a,"--z-max")){o.z_max=parse_int(v,"z-max",-29999984,29999984);o.slice=1;}
        else {fprintf(stderr,"Unknown option %s\n",a);exit(2);}
    }
    if(!have_seed){usage(argv[0]);exit(2);}
    if((o.template_width==0)!=(o.template_depth==0)){
        fprintf(stderr,"Template width and depth must be supplied together.\n");exit(2);
    }
    if(o.slice && (o.count<0||o.x_min>o.x_max||o.z_min>o.z_max)){fprintf(stderr,"Invalid slice bounds\n");exit(2);}
    if(o.strict_nearest && (o.start_ring<0||o.ring_count<1)){fprintf(stderr,"Invalid ring range\n");exit(2);}
    int64_t width=(int64_t)floor_div(o.radius,512)-floor_div(-o.radius,512)+1;
    if(width*width>5000000){fprintf(stderr,"Search covers too many regions; reduce --radius (maximum 5,000,000 regions).\n");exit(2);}
    return o;
}

static int strict_cell(const Opts *o, int rx, int rz, int lo, int hi, int zlo, int zhi,
                       lysh_phase2 *p2, lysh_biome *biome, Hit *h,
                       uint64_t *placed, uint64_t *biome_pass, uint64_t *height_pass) {
    if(rx<lo||rx>hi||rz<zlo||rz>zhi)return 0;
    lysh_chunkpos pos=region_candidate(o->seed,rx,rz,OUTPOST_SPACING,OUTPOST_SEPARATION,OUTPOST_SALT);
    int x=pos.chunkX*16,z=pos.chunkZ*16;
    if(x<o->x_min||x>o->x_max||z<o->z_min||z>o->z_max)return 0;
    if(!legacy_frequency(o->seed,pos.chunkX,pos.chunkZ)||near_village_candidate(o->seed,pos.chunkX,pos.chunkZ))return 0;
    (*placed)++;
    lysh_biome_result br;
    lysh_swamp_hut_biome_ok(biome,&p2->terrain,x,z,terrain_top,p2,&br);
    if(!o->skip_biome&&!outpost_biome(br.winner))return 0;
    (*biome_pass)++;
    /* StructurePoolBasedGenerator first creates the rotated base-plate box,
       then calls getHeightOnGround at integer (minX+maxX)/2,(minZ+maxZ)/2.
       This is the actual WORLD_SURFACE_WG probe, not the start chunk origin. */
    start_projection(o->seed,pos.chunkX,pos.chunkZ,o->template_width,o->template_depth,
                     &h->sample_x,&h->sample_z,&h->rotation);
    h->y=terrain_top(p2,h->sample_x,h->sample_z);
    h->cx=pos.chunkX;h->cz=pos.chunkZ;h->x=x;h->z=z;h->biome=br.winner;
    /* The official 1.21.8 watchtower chest floor is +14 above base_plate.
       Empirical vanilla check: a real cave outpost can have elevated
       footprint samples while its generated centre is deep underground.
       Therefore the tower spawn centre is the sole acceptance condition.
       Extra footprint probes are deliberately omitted for throughput. */
    if(h->y-1+o->tower_center_offset_y>=o->max_y)return 0;
    h->max_surface_y=h->y;
    (*height_pass)++;
    return 1;
}

/* A ring is the atomic unit of centre-out ordering.  Workers may evaluate
 * cells within it concurrently, but the caller never advances to the next
 * ring before all of its results have been merged.  This is the same staged,
 * worker-private model used by LowYSwampHut's search.c. */
typedef struct {
    const Opts *o;
    int ring, center_rx, center_rz, lo, hi, zlo, zhi;
    int64_t first, last;
    Hit *hits;
    int kept, capacity;
    uint64_t placed, biome_pass, height_pass;
    lysh_phase2 p2;
    lysh_biome biome;
    int model_ready;
} StrictWorker;
typedef struct { int threads; StrictWorker *workers; } StrictSession;

static void ring_position(int center_rx,int center_rz,int ring,int64_t index,int *rx,int *rz) {
    if(ring==0){*rx=center_rx;*rz=center_rz;return;}
    int side=(int)(index/(2*ring)), step=(int)(index%(2*ring));
    *rx=center_rx;*rz=center_rz;
    if(side==0){*rx+=ring;*rz-=ring;*rz+=step;}
    else if(side==1){*rx+=ring;*rz+=ring;*rx-=step;}
    else if(side==2){*rx-=ring;*rz+=ring;*rz-=step;}
    else {*rx-=ring;*rz-=ring;*rx+=step;}
}

static void strict_worker_run(StrictWorker *w) {
    for(int64_t index=w->first;index<w->last;index++){
        int rx,rz;Hit hit;
        ring_position(w->center_rx,w->center_rz,w->ring,index,&rx,&rz);
        if(strict_cell(w->o,rx,rz,w->lo,w->hi,w->zlo,w->zhi,&w->p2,&w->biome,&hit,
                       &w->placed,&w->biome_pass,&w->height_pass))
            keep_nearest(w->hits,&w->kept,w->capacity,&hit,w->o->center_x,w->o->center_z);
    }
}

#if defined(_WIN32)
static DWORD WINAPI strict_worker_trampoline(LPVOID value) { strict_worker_run((StrictWorker *)value);return 0; }
#else
static void *strict_worker_trampoline(void *value) { strict_worker_run((StrictWorker *)value);return NULL; }
#endif

static StrictSession *strict_session_open(const Opts *o) {
    int threads=o->threads?o->threads:cpu_count();
    if(threads<1)threads=1;
    StrictSession *session=calloc(1,sizeof(*session));
    if(!session)return NULL;
    session->workers=calloc((size_t)threads,sizeof(*session->workers));
    if(!session->workers){free(session);return NULL;}
    session->threads=threads;
    for(int t=0;t<threads;t++){
        StrictWorker *w=&session->workers[t];
        w->o=o;w->hits=calloc((size_t)o->limit,sizeof(*w->hits));w->capacity=o->limit;
        if(!w->hits){
            for(int j=0;j<t;j++){lysh_phase2_free(&session->workers[j].p2);free(session->workers[j].hits);}
            free(session->workers);free(session);return NULL;
        }
        lysh_phase2_init(&w->p2,o->seed,o->large_biomes);
        lysh_phase2_set_column_top(&w->p2,aquifer_column_top,&w->p2.terrain);
        lysh_phase2_set_carvers(&w->p2,0);
        lysh_biome_init(&w->biome,o->seed,o->large_biomes,LYSH_BIOME_TREE_1_21_5);
        w->model_ready=1;
    }
    return session;
}
static void strict_session_close(StrictSession *session) {
    if(!session)return;
    for(int t=0;t<session->threads;t++){
        if(session->workers[t].model_ready)lysh_phase2_free(&session->workers[t].p2);
        free(session->workers[t].hits);
    }
    free(session->workers);free(session);
}

static int scan_strict_ring(StrictSession *session,int ring,int center_rx,int center_rz,
                            int lo,int hi,int zlo,int zhi,Hit *output,int capacity,
                            uint64_t *placed,uint64_t *biome_pass,uint64_t *height_pass) {
    int64_t cells=ring==0?1:8LL*ring;
    const Opts *o=session->workers[0].o;
    int threads=session->threads;
    if((int64_t)threads>cells)threads=(int)cells;
#if defined(_WIN32)
    HANDLE *handles=calloc((size_t)threads,sizeof(*handles));
#else
    pthread_t *handles=calloc((size_t)threads,sizeof(*handles));
#endif
    if(!handles){perror("calloc");return -1;}
    for(int t=0;t<threads;t++){
        StrictWorker *w=&session->workers[t];
        w->ring=ring;w->center_rx=center_rx;w->center_rz=center_rz;
        w->lo=lo;w->hi=hi;w->zlo=zlo;w->zhi=zhi;w->first=cells*t/threads;w->last=cells*(t+1)/threads;
        w->capacity=capacity;w->kept=0;w->placed=0;w->biome_pass=0;w->height_pass=0;
    }
    for(int t=0;t<threads;t++){
        if(threads==1){strict_worker_run(&session->workers[t]);continue;}
#if defined(_WIN32)
        handles[t]=CreateThread(NULL,0,strict_worker_trampoline,&session->workers[t],0,NULL);
        if(!handles[t])strict_worker_run(&session->workers[t]);
#else
        if(pthread_create(&handles[t],NULL,strict_worker_trampoline,&session->workers[t])!=0)strict_worker_run(&session->workers[t]);
#endif
    }
    int output_count=0;
    for(int t=0;t<threads;t++){
#if defined(_WIN32)
        if(handles[t]){WaitForSingleObject(handles[t],INFINITE);CloseHandle(handles[t]);}
#else
        if(threads>1 && handles[t])pthread_join(handles[t],NULL);
#endif
        *placed+=session->workers[t].placed;*biome_pass+=session->workers[t].biome_pass;*height_pass+=session->workers[t].height_pass;
        for(int j=0;j<session->workers[t].kept;j++)keep_nearest(output,&output_count,capacity,&session->workers[t].hits[j],o->center_x,o->center_z);
    }
    free(handles);return output_count;
}

int main(int argc,char **argv) {
    Opts o=options(argc,argv);
    Hit *hits=calloc((size_t)o.limit,sizeof(*hits));
    if(!hits){perror("calloc");return 1;}
    lysh_phase2 p2={0};lysh_biome biome;
    if(!o.candidates_only&&!o.strict_nearest){
        lysh_phase2_init(&p2,o.seed,o.large_biomes);
        lysh_phase2_set_column_top(&p2,aquifer_column_top,&p2.terrain);
        lysh_phase2_set_carvers(&p2,0);
        /* The supplied LowYSwampHut core labels the 1.21.5~26.1 biome tree as
           the closest model to 1.21.8; it is not a version-exact oracle. */
        lysh_biome_init(&biome,o.seed,o.large_biomes,LYSH_BIOME_TREE_1_21_5);
    }
    uint64_t region_count=0,placed_count=0,valid_biome=0,below_y=0;
    int kept=0;
    int lo=o.slice?floor_div(o.x_min-368,512):floor_div(-o.radius,512);
    int hi=o.slice?floor_div(o.x_max,512):floor_div(o.radius,512);
    int zlo=o.slice?floor_div(o.z_min-368,512):lo;
    int zhi=o.slice?floor_div(o.z_max,512):hi;
    int64_t width=(int64_t)hi-lo+1,total=width*((int64_t)zhi-zlo+1);
    int64_t begin=o.slice?o.start:0,end=o.slice?o.start+o.count:total;
    if(begin<0||end<begin||end>total){fprintf(stderr,"Slice outside grid\n");return 2;}
    if(o.strict_nearest){
        int cr=floor_div(o.center_x,512),czr=floor_div(o.center_z,512);
        int64_t next_ring=o.start_ring;
        StrictSession *session=strict_session_open(&o);
        if(!session){perror("strict worker session");free(hits);return 1;}
        for(int64_t ring=o.start_ring;ring<o.start_ring+o.ring_count;ring++){
            int remaining=o.limit-kept;
            Hit *ring_hits=calloc((size_t)remaining,sizeof(*ring_hits));
            if(!ring_hits){perror("calloc");strict_session_close(session);free(hits);return 1;}
            int ring_kept=scan_strict_ring(session,(int)ring,cr,czr,lo,hi,zlo,zhi,ring_hits,remaining,
                                           &placed_count,&valid_biome,&below_y);
            if(ring_kept<0){free(ring_hits);strict_session_close(session);free(hits);return 1;}
            region_count+=(ring==0?1:8*(uint64_t)ring);
            for(int j=0;j<ring_kept;j++)hits[kept++]=ring_hits[j];
            free(ring_hits);
            next_ring=ring+1;
            if(kept>=o.limit)break;
        }
        if(o.json){
            printf("{\"matches\":%" PRIu64 ",\"biome_passes\":%" PRIu64 ",\"height_passes\":%" PRIu64 ",\"next_ring\":%" PRId64 ",\"stopped_early\":%s,\"model_fingerprint\":\"lowyswamphut-approx-1.21.8-centre-strict-single-sample\",\"rows\":[",placed_count,valid_biome,below_y,next_ring,kept>=o.limit?"true":"false");
            for(int j=0;j<kept;j++){Hit *h=&hits[j];int maximum=h->max_surface_y,rot=h->rotation;if(j)putchar(',');
                printf("{\"chunk_x\":%d,\"chunk_z\":%d,\"projected_surface_y\":%d,\"projected_base_plate_y\":%d,\"projected_structure_center_y\":%d,\"projected_base_plate_max_y\":%d,\"footprint_sample_count\":1,\"sample_x\":%d,\"sample_z\":%d,\"rotation\":%d,\"biome_id\":%d,\"classification\":\"estimated_only\"}",h->cx,h->cz,h->y,h->y-1,h->y-1+o.tower_center_offset_y,maximum-1,h->sample_x,h->sample_z,rot,h->biome);
            }
            puts("]}");strict_session_close(session);free(hits);return 0;
        }
        strict_session_close(session);
    }
    for(int64_t index=begin;!o.strict_nearest&&index<end;index++){
        int rx=lo+(int)(index%width),rz=zlo+(int)(index/width);
        region_count++;
        lysh_chunkpos pos=region_candidate(o.seed,rx,rz,OUTPOST_SPACING,OUTPOST_SEPARATION,OUTPOST_SALT);
        int x=pos.chunkX*16,z=pos.chunkZ*16;
        if(o.slice ? (x<o.x_min||x>o.x_max||z<o.z_min||z>o.z_max) :
                     (x<-o.radius||x>o.radius||z<-o.radius||z>o.radius))continue;
        if(!legacy_frequency(o.seed,pos.chunkX,pos.chunkZ))continue;
        if(near_village_candidate(o.seed,pos.chunkX,pos.chunkZ))continue;
        placed_count++;
        Hit h={.cx=pos.chunkX,.cz=pos.chunkZ,.x=x,.z=z,.y=INT_MAX,
               .max_surface_y=INT_MAX,.biome=-1,.sample_x=x+8,.sample_z=z+8,.rotation=-1};
        if(o.template_width){
            start_projection(o.seed,h.cx,h.cz,o.template_width,o.template_depth,
                             &h.sample_x,&h.sample_z,&h.rotation);
        }
        if(!o.candidates_only){
            lysh_biome_result br;
            lysh_swamp_hut_biome_ok(&biome,&p2.terrain,x,z,terrain_top,&p2,&br);
            h.biome=br.winner;
            if(!o.skip_biome&&!outpost_biome(h.biome))continue;
            valid_biome++;
            h.y=terrain_top(&p2,h.sample_x,h.sample_z);
            /* Vanilla rigid base plate getGroundLevelDelta() = 1.  With a
             * supplied template the user's cutoff is the BASEPLATE height.
             * Do not silently filter on the surface one block higher. */
            int cutoff_y = o.template_width ? h.y - 1 : h.y;
            if(cutoff_y>o.max_y)continue;
        }else valid_biome++;
        below_y++;
        if(kept<o.limit)hits[kept++]=h;
        else if(!o.candidates_only){
            int worst=0;
            for(int j=1;j<kept;j++)if(hitcmp(&hits[j],&hits[worst])>0)worst=j;
            if(hitcmp(&h,&hits[worst])<0)hits[worst]=h;
        }
    }
    if(!o.candidates_only)qsort(hits,(size_t)kept,sizeof(*hits),hitcmp);
    FILE *out=stdout;
    if(o.json){
        printf("{\"matches\":%" PRIu64 ",\"biome_passes\":%" PRIu64 ",\"height_passes\":%" PRIu64 ",\"model_fingerprint\":\"lowyswamphut-approx-1.21.8\",\"rows\":[",placed_count,valid_biome,below_y);
        for(int j=0;j<kept;j++){Hit *h=&hits[j];if(j)putchar(',');
            printf("{\"chunk_x\":%d,\"chunk_z\":%d,\"projected_surface_y\":%d,\"projected_base_plate_y\":%d,\"sample_x\":%d,\"sample_z\":%d,\"rotation\":%d,\"biome_id\":%d,\"classification\":\"estimated_only\"}",h->cx,h->cz,h->y,h->y-1,h->sample_x,h->sample_z,h->rotation,h->biome);}
        puts("]}"); if(!o.candidates_only&&!o.strict_nearest)lysh_phase2_free(&p2);free(hits);return 0;
    }
    if(o.csv){out=fopen(o.csv,"w");if(!out){perror(o.csv);if(!o.candidates_only&&!o.strict_nearest)lysh_phase2_free(&p2);free(hits);return 1;}}
    if(o.candidates_only) fprintf(out,"version,seed,chunk_x,chunk_z,x,z,projected_surface_y,biome_id,classification\n");
    else fprintf(out,"version,seed,chunk_x,chunk_z,x,z,projected_surface_y,biome_id,classification,sample_x,sample_z,rotation,projected_base_plate_y\n");
    for(int j=0;j<kept;j++){
        Hit *h=&hits[j];
        fprintf(out,"1.21.8,%" PRId64 ",%d,%d,%d,%d,",(int64_t)o.seed,h->cx,h->cz,h->x,h->z);
        if(o.candidates_only)fprintf(out,"unknown,unknown,placement_candidate\n");
        else if(o.template_width)
            fprintf(out,"%d,%d,estimated_only,%d,%d,%d,%d\n",
                    h->y,h->biome,h->sample_x,h->sample_z,h->rotation,h->y-1);
        else fprintf(out,"%d,%d,estimated_only,%d,%d,,\n",h->y,h->biome,h->sample_x,h->sample_z);
    }
    if(o.csv)fclose(out);
    fprintf(stderr,"regions=%" PRIu64 " placement_candidates=%" PRIu64 " biome_pass=%" PRIu64 " height_pass=%" PRIu64 " output=%d mode=%s\n",region_count,placed_count,valid_biome,below_y,kept,o.candidates_only?"placement":"terrain_estimate");
    if(!o.candidates_only&&!o.strict_nearest)lysh_phase2_free(&p2);
    free(hits);return 0;
}
