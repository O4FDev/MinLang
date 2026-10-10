
#define MINYAR_RC_TESTING
#include "runtime/minyar_runtime.c"
#include <assert.h>
#include "llvm_symbols.h"
static size_t tokenizer_lists;
static size_t tokenizer_locations;
static size_t tokenizer_source_reads;
static MinyarText *tokenizer_source;
static MinyarRecord *tokenizer_map;
static size_t tokenizer_map_reads;
long long probe_source_map_field(MinyarRecord *record,long long field) {
 if(record==tokenizer_map) tokenizer_map_reads++;
 return minyar_record_get(record,field);
}
int probe_source_character(MinyarText *text, long long position) {
 if(text==tokenizer_source) tokenizer_source_reads++;
 return minyar_text_character_at(text,position);
}
MinyarList *probe_tokenizer_list(void) { tokenizer_lists++; return minyar_list_new(); }
extern MinyarText *original_source_location(long long, long long);
MinyarText *probe_source_location(long long line, long long column) {
 tokenizer_locations++; return original_source_location(line,column);
}
extern MinyarRecord *newSourceMap(void) MINYAR_TEST_LANGUAGE_SYMBOL(newSourceMap);
extern void tokenize(MinyarText *, MinyarList *, MinyarList *, MinyarRecord *) MINYAR_TEST_LANGUAGE_SYMBOL(tokenize);
static void drain(void) {
#ifdef MINYAR_BOUNDED_RC
 while(rc_pending_count) minyar_rc_poll(1024);
#endif
 assert(rc_pending_count==0); assert(rc_frames==NULL);
}
int main(int argc,char **argv) {
 assert(argc==2||argc==3);size_t stable_bytes=0,stable_objects=0;
 for(int pass=0;pass<3;pass++) {
  FILE *f=fopen(argv[1],"rb");assert(f);assert(!fseek(f,0,SEEK_END));long n=ftell(f);assert(n>=0);assert(!fseek(f,0,SEEK_SET));
  unsigned char *bytes=new_bytes(n);assert(fread(bytes,1,(size_t)n,f)==(size_t)n);bytes[n]=0;fclose(f);
  MinyarText *source=new_text(bytes,n,-1);
  MinyarList *kinds=minyar_list_new(),*texts=minyar_list_new();
  MinyarRecord *lines=newSourceMap();
  MinyarList *coordinates=(MinyarList *)(intptr_t)minyar_record_get(lines,0);
  MinyarList *paths=(MinyarList *)(intptr_t)minyar_record_get(lines,1);
  MinyarList *origins=(MinyarList *)(intptr_t)minyar_record_get(lines,2);
  MinyarList *path_indices=(MinyarList *)(intptr_t)minyar_record_get(lines,3);
  minyar_list_references(texts);
  tokenizer_source=source;tokenizer_source_reads=0;tokenizer_map=lines;tokenizer_map_reads=0;
  tokenize(source,kinds,texts,lines);
  if(argc==3) assert(tokenizer_source_reads <= strtoull(argv[2],NULL,10) && "identifier scanning must read each character once plus one delimiter lookahead");
  assert(tokenizer_map_reads<=1 && "the lexer must borrow its coordinate buffer once rather than once per token");
  tokenizer_source=NULL;tokenizer_map=NULL;
  assert(tokenizer_locations==0 && "successful tokenization must not format diagnostic locations");
  /* Output owners must survive both source retirement and complete deferred cleanup. */
  minyar_rc_release(source);drain();
  assert(kinds->length==texts->length&&kinds->length*2==coordinates->length);
  assert(paths->length==1&&origins->length==0&&path_indices->length==0);
  MinyarText *alias=NULL;unsigned char *expected=NULL;size_t alias_bytes=0;
  for(long long i=0;i<kinds->length;i++) {
   MinyarText *text=(MinyarText *)(intptr_t)texts->values[i];
   if(pass==0) {printf("%lld\t%lld, column %lld\t",kinds->values[i],coordinates->values[i*2],coordinates->values[i*2+1]);for(long long j=0;j<text->byte_length;j++)printf("%02x",text->bytes[j]);putchar('\n');}
   if(!alias&&kinds->values[i]==3) {alias=text;minyar_rc_retain(alias);alias_bytes=(size_t)alias->byte_length;expected=malloc(alias_bytes+1);assert(expected);memcpy(expected,alias->bytes,alias_bytes);}
  }
  minyar_rc_release(kinds);minyar_rc_release(texts);minyar_rc_release(lines);drain();
  if(alias) {assert((size_t)alias->byte_length==alias_bytes);assert(!memcmp(alias->bytes,expected,alias_bytes));free(expected);minyar_rc_release(alias);drain();}
  assert(rc_object_count==rc_immortal_object_count);
  if(pass==0){stable_bytes=rc_bytes;stable_objects=rc_object_count;}else{assert(rc_bytes==stable_bytes);assert(rc_object_count==stable_objects);}
 }
 fprintf(stderr,"TOKEN_LISTS=%zu\n",tokenizer_lists);
 fprintf(stderr,"OWNERS clean=1 retained_objects=%zu retained_bytes=%zu\n",stable_objects,stable_bytes);
}
