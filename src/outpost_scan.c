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

#include "rng.h"
#include "structure.h"
#include "phase2.h"
#include "biome.h"
#include "column_top.h"

enum { OUTPOST_SPACING=32, OUTPOST_SEPARATION=8, OUTPOST_SALT=165745296,
       VILLAGE_SPACING=34, VILLAGE_SEPARATION=8, VILLAGE_SALT=10387312 };

typedef struct { int cx, cz, x, z, y, biome, sample_x, sample_z, rotation; } Hit;
typedef struct { uint64_t seed; int radius,max_y,limit,large_biomes,candidates_only,skip_biome,template_width,template_depth; const char *csv; } Opts;

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

/* ── Biome whitelist (cubiomes IDs, vanilla 1.21.8 tag) ── */
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
static void usage(const char *name) {
    printf("Usage: %s --seed SIGNED_LONG [--radius BLOCKS] [--max-y Y] [--top N] [--csv FILE] [--candidates-only] [--skip-biome] [--large-biomes] [--template-width N --template-depth N]\n",name);
    puts("Defaults: radius=8192 blocks, max-y=64, top=25, version=1.21.8 approximate noise.");
    puts("With a template: --max-y applies to projected BASEPLATE Y (surface - ground-level delta=1).");
    puts("Without a template: --max-y filters the approximate surface Y only.");
    puts("Output is NOT a verified tower Y, nor a confirmed structure in an ungenerated vanilla world.");
}
static Opts options(int argc,char **argv) {
    Opts o={0,8192,64,25,0,0,0,0,0,NULL};int have_seed=0;
    for(int i=1;i<argc;i++) {
        const char *a=argv[i];
        if(!strcmp(a,"--help")||!strcmp(a,"-h")){usage(argv[0]);exit(0);}
        if(!strcmp(a,"--candidates-only")){o.candidates_only=1;continue;}
        if(!strcmp(a,"--skip-biome")){o.skip_biome=1;continue;}
        if(!strcmp(a,"--large-biomes")){o.large_biomes=1;continue;}
        if(i+1>=argc){fprintf(stderr,"Missing value for %s\n",a);exit(2);}const char *v=argv[++i];
        if(!strcmp(a,"--seed")){o.seed=(uint64_t)parse_long(v,"seed");have_seed=1;}
        else if(!strcmp(a,"--radius"))o.radius=parse_int(v,"radius",0,30000000);
        else if(!strcmp(a,"--max-y"))o.max_y=parse_int(v,"max-y",-64,320);
        else if(!strcmp(a,"--top"))o.limit=parse_int(v,"top",1,100000);
        else if(!strcmp(a,"--template-width"))o.template_width=parse_int(v,"template-width",1,128);
        else if(!strcmp(a,"--template-depth"))o.template_depth=parse_int(v,"template-depth",1,128);
        else if(!strcmp(a,"--csv"))o.csv=v;
        else {fprintf(stderr,"Unknown option %s\n",a);exit(2);}
    }
    if(!have_seed){usage(argv[0]);exit(2);}
    if((o.template_width==0)!=(o.template_depth==0)){
        fprintf(stderr,"Template width and depth must be supplied together.\n");exit(2);
    }
    int64_t width=(int64_t)floor_div(o.radius,512)-floor_div(-o.radius,512)+1;
    if(width*width>5000000){fprintf(stderr,"Search covers too many regions; reduce --radius (maximum 5,000,000 regions).\n");exit(2);}
    return o;
}
int main(int argc,char **argv) {
    Opts o=options(argc,argv);
    Hit *hits=calloc((size_t)o.limit,sizeof(*hits));
    if(!hits){perror("calloc");return 1;}
    lysh_phase2 p2;lysh_biome biome;
    if(!o.candidates_only){
        lysh_phase2_init(&p2,o.seed,o.large_biomes);
        lysh_phase2_set_column_top(&p2,aquifer_column_top,&p2.terrain);
        lysh_phase2_set_carvers(&p2,0);
        /* The supplied LowYSwampHut core labels the 1.21.5~26.1 biome tree as
           the closest model to 1.21.8; it is not a version-exact oracle. */
        lysh_biome_init(&biome,o.seed,o.large_biomes,LYSH_BIOME_TREE_1_21_5);
    }
    uint64_t region_count=0,placed_count=0,valid_biome=0,below_y=0;
    int kept=0;
    int lo=floor_div(-o.radius,512),hi=floor_div(o.radius,512);
    for(int rz=lo;rz<=hi;rz++)for(int rx=lo;rx<=hi;rx++){
        region_count++;
        lysh_chunkpos pos=region_candidate(o.seed,rx,rz,OUTPOST_SPACING,OUTPOST_SEPARATION,OUTPOST_SALT);
        int x=pos.chunkX*16,z=pos.chunkZ*16;
        if(x < -o.radius||x > o.radius||z < -o.radius||z > o.radius)continue;
        if(!legacy_frequency(o.seed,pos.chunkX,pos.chunkZ))continue;
        if(near_village_candidate(o.seed,pos.chunkX,pos.chunkZ))continue;
        placed_count++;
        Hit h={pos.chunkX,pos.chunkZ,x,z,INT_MAX,-1,x+8,z+8,-1};
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
    if(o.csv){out=fopen(o.csv,"w");if(!out){perror(o.csv);if(!o.candidates_only)lysh_phase2_free(&p2);free(hits);return 1;}}
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
    if(!o.candidates_only)lysh_phase2_free(&p2);
    free(hits);return 0;
}
