/* Time-annotations by cbb-analyzer 
 * Using WCET library for target Atmega128 from 2018-02-16_13:40:25
 */
#ifdef WCETREPLAY
  #define EXTRA_INSTRUCTION __asm__("nop");
#else
  #define EXTRA_INSTRUCTION /* nada */
#endif
#define TIC(X) ({timeElapsed += (X); EXTRA_INSTRUCTION})

unsigned long timeElapsed = 0;
int swi120(int c)
{TIC(14); 
	int i;
	for (i=0; TIC(537), i<120; i++) {
		switch (i) {
			case 0: c++; break;
			case 1: TIC(4), c++; break;
			case 2: c++; break;
			case 3: c++; break;
			case 4: TIC(4), c++; break;
			case 5: c++; break;
			case 6: c++; break;
			case 7: c++; break;
			case 8: TIC(2), c++; break;
			case 9: c++; break;
			case 10: c++; break;
			case 11: c++; break;
			case 12: TIC(4), c++; break;
			case 13: c++; break;
			case 14: c++; break;
			case 15: c++; break;
			case 16: TIC(4), c++; break;
			case 17: c++; break;
			case 18: c++; break;
			case 19: TIC(4), c++; break;
			case 20: c++; break;
			case 21: c++; break;
			case 22: c++; break;
			case 23: TIC(4), c++; break;
			case 24: c++; break;
			case 25: c++; break;
			case 26: c++; break;
			case 27: TIC(4), c++; break;
			case 28: c++; break;
			case 29: c++; break;
			case 30: c++; break;
			case 31: TIC(4), c++; break;
			case 32: c++; break;
			case 33: c++; break;
			case 34: TIC(4), c++; break;
			case 35: c++; break;
			case 36: c++; break;
			case 37: c++; break;
			case 38: TIC(4), c++; break;
			case 39: c++; break;
			case 40: c++; break;
			case 41: c++; break;
			case 42: TIC(4), c++; break;
			case 43: c++; break;
			case 44: c++; break;
			case 45: c++; break;
			case 46: TIC(4), c++; break;
			case 47: c++; break;
			case 48: c++; break;
			case 49: TIC(4), c++; break;
			case 50: c++; break;
			case 51: c++; break;
			case 52: c++; break;
			case 53: TIC(4), c++; break;
			case 54: c++; break;
			case 55: c++; break;
			case 56: c++; break;
			case 57: TIC(4), c++; break;
			case 58: c++; break;
			case 59: c++; break;
			case 60: c++; break;
			case 61: TIC(4), c++; break;
			case 62: c++; break;
			case 63: c++; break;
			case 64: TIC(4), c++; break;
			case 65: c++; break;
			case 66: c++; break;
			case 67: c++; break;
			case 68: TIC(4), c++; break;
			case 69: c++; break;
			case 70: c++; break;
			case 71: c++; break;
			case 72: TIC(4), c++; break;
			case 73: c++; break;
			case 74: c++; break;
			case 75: c++; break;
			case 76: TIC(4), c++; break;
			case 77: c++; break;
			case 78: c++; break;
			case 79: TIC(4), c++; break;
			case 80: c++; break;
			case 81: c++; break;
			case 82: c++; break;
			case 83: TIC(4), c++; break;
			case 84: c++; break;
			case 85: c++; break;
			case 86: c++; break;
			case 87: TIC(4), c++; break;
			case 88: c++; break;
			case 89: c++; break;
			case 90: c++; break;
			case 91: TIC(4), c++; break;
			case 92: c++; break;
			case 93: c++; break;
			case 94: TIC(4), c++; break;
			case 95: c++; break;
			case 96: c++; break;
			case 97: c++; break;
			case 98: TIC(4), c++; break;
			case 99: c++; break;
			case 100: c++; break;
			case 101: c++; break;
			case 102: TIC(4), c++; break;
			case 103: c++; break;
			case 104: c++; break;
			case 105: c++; break;
			case 106: TIC(4), c++; break;
			case 107: c++; break;
			case 108: c++; break;
			case 109: c++; break;
			case 110: c++; break;
			case 111: c++; break;
			case 112: c++; break;
			case 113: c++; break;
			case 114: TIC(4), c++; break;
			case 115: c++; break;
			case 116: c++; break;
			case 117: c++; break;
			case 118: c++; break;
			case 119: c++; break;
			default: c--; break;
		}
	}
	TIC(0); return c;
}


int swi50(int c)
{TIC(54); 
	int i;
	for (i=0; TIC(213), i<50; i++) {
		switch (i) {
			case 0: c++; break;
			case 1: TIC(4), c++; break;
			case 2: c++; break;
			case 3: c++; break;
			case 4: TIC(2), c++; break;
			case 5: c++; break;
			case 6: c++; break;
			case 7: c++; break;
			case 8: TIC(4), c++; break;
			case 9: c++; break;
			case 10: c++; break;
			case 11: c++; break;
			case 12: TIC(4), c++; break;
			case 13: c++; break;
			case 14: c++; break;
			case 15: TIC(4), c++; break;
			case 16: TIC(4), c++; break;
			case 17: c++; break;
			case 18: c++; break;
			case 19: TIC(4), c++; break;
			case 20: c++; break;
			case 21: c++; break;
			case 22: c++; break;
			case 23: TIC(4), c++; break;
			case 24: c++; break;
			case 25: c++; break;
			case 26: c++; break;
			case 27: TIC(4), c++; break;
			case 28: c++; break;
			case 29: c++; break;
			case 30: TIC(4), c++; break;
			case 31: TIC(4), c++; break;
			case 32: TIC(4), c++; break;
			case 33: c++; break;
			case 34: TIC(4), c++; break;
			case 35: c++; break;
			case 36: c++; break;
			case 37: c++; break;
			case 38: TIC(4), c++; break;
			case 39: c++; break;
			case 40: TIC(4), c++; break;
			case 41: c++; break;
			case 42: TIC(4), c++; break;
			case 43: c++; break;
			case 44: c++; break;
			case 45: c++; break;
			case 46: TIC(6), c++; break;
			case 47: c++; break;
			case 48: c++; break;
			case 49: c++; break;
			case 50: c++; break;
			case 51: c++; break;
			case 52: c++; break;
			case 53: c++; break;
			case 54: c++; break;
			case 55: c++; break;
			case 56: c++; break;
			case 57: c++; break;
			case 58: c++; break;
			case 59: c++; break;
			default: c--; break;
		}
	}
	TIC(0); return c;
}


int swi10(int c)
{TIC(14); 
	int i;
	for (i=0; TIC(53), i<10; i++) {
		switch (i) {
			case 0: TIC(4), c++; break;
			case 1: TIC(4), c++; break;
			case 2: TIC(4), c++; break;
			case 3: TIC(4), c++; break;
			case 4: TIC(4), c++; break;
			case 5: TIC(4), c++; break;
			case 6: TIC(4), c++; break;
			case 7: TIC(4), c++; break;
			case 8: TIC(4), c++; break;
			case 9: c++; break;
			default: c--; break;
		}
	}
	TIC(0); return c;
}

int main() 
{TIC(0); 
	TIC(77)/* TODO: missing time from swi10 */; volatile int cnt=0;

	cnt=swi10(cnt);
	cnt=swi50(cnt);
	cnt=swi120(cnt);

	/* printf("cnt: %d\n", cnt); */

	return cnt;

}
